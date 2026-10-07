"""Export and comparison behavior, with the file path treated as the security boundary."""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from tidal_mcp.client import TidalClient
from tidal_mcp.exceptions import ExportError, TidalClientError
from tidal_mcp.exports import render_json, render_m3u, safe_filename, write_export
from tidal_mcp.models import Track


def track(track_id: str, *, title: str = "Title", artist: str = "Artist", duration: int = 100):
    return Track(
        id=track_id,
        title=title,
        artist=artist,
        duration_seconds=duration,
        url=f"https://tidal.com/browse/track/{track_id}",
    )


@pytest.mark.parametrize(
    ("requested", "expected"),
    [
        ("../../etc/passwd", "etc-passwd.json"),
        ("/etc/passwd", "etc-passwd.json"),
        ("my list/../../x", "my-list-..-..-x.json"),
        ("..", "tidal-playlist.json"),
        (".", "tidal-playlist.json"),
        ("", "tidal-playlist.json"),
        ("with spaces", "with-spaces.json"),
        ("semi;colon", "semi-colon.json"),
        ("back\\slash", "back-slash.json"),
        ("already.json", "already.json"),
    ],
)
def test_export_names_can_never_escape_the_directory(requested: str, expected: str) -> None:
    assert safe_filename(requested, suffix=".json") == expected


def test_export_names_are_bounded_and_keep_the_extension() -> None:
    name = safe_filename("a" * 200, suffix=".m3u")
    assert len(name) <= 80 + len(".m3u")
    assert name.endswith(".m3u")


def test_export_names_appending_the_extension_is_idempotent() -> None:
    once = safe_filename("mix", suffix=".json")
    assert safe_filename(once, suffix=".json") == once


def test_json_export_contains_public_metadata_only() -> None:
    rendered = json.loads(render_json([track("1", title="Song", artist="Band")]))
    assert rendered["track_count"] == 1
    assert rendered["tracks"][0]["title"] == "Song"
    assert rendered["tracks"][0]["url"].endswith("/track/1")
    assert "session" not in json.dumps(rendered)


def test_m3u_export_points_at_tidal_and_uses_the_extended_headers() -> None:
    rendered = render_m3u([track("1", title="Song", artist="Band", duration=210)])
    lines = rendered.strip().splitlines()
    assert lines[0] == "#EXTM3U"
    assert lines[1] == "#EXTINF:210,Band - Song"
    assert lines[2] == "https://tidal.com/browse/track/1"


def test_m3u_marks_an_unknown_duration_as_minus_one() -> None:
    item = track("1")
    item = item.model_copy(update={"duration_seconds": None})
    assert "#EXTINF:-1," in render_m3u([item])


def test_write_export_creates_a_private_file(tmp_path: Path) -> None:
    directory = tmp_path / "exports"
    result = write_export(
        export_dir=directory,
        playlist_id="p1",
        title="My Mix",
        tracks=[track("1"), track("2")],
        export_format="json",
        name=None,
        truncated=False,
    )
    target = Path(result.path)
    assert target.exists()
    assert target.name == "My-Mix.json"
    assert target.stat().st_mode & 0o777 == 0o600
    assert directory.stat().st_mode & 0o777 == 0o700
    assert result.track_count == 2
    assert result.bytes_written == target.stat().st_size
    assert result.format == "json"


def test_write_export_refuses_to_overwrite(tmp_path: Path) -> None:
    directory = tmp_path / "exports"
    arguments = {
        "export_dir": directory,
        "playlist_id": "p1",
        "title": "Mix",
        "tracks": [track("1")],
        "export_format": "json",
        "name": None,
        "truncated": False,
    }
    write_export(**arguments)
    with pytest.raises(ExportError, match="already exists"):
        write_export(**arguments)


def test_write_export_leaves_no_partial_file_behind_on_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    directory = tmp_path / "exports"

    def explode(*_args: object, **_kwargs: object) -> None:
        raise OSError("disk full")

    monkeypatch.setattr(Path, "replace", explode)
    with pytest.raises(OSError):
        write_export(
            export_dir=directory,
            playlist_id="p1",
            title="Mix",
            tracks=[track("1")],
            export_format="json",
            name=None,
            truncated=False,
        )
    assert [entry.name for entry in directory.iterdir()] == []


def test_export_reports_truncation(tmp_path: Path) -> None:
    result = write_export(
        export_dir=tmp_path / "exports",
        playlist_id="p1",
        title=None,
        tracks=[track("1")],
        export_format="m3u",
        name=None,
        truncated=True,
    )
    assert result.truncated is True
    assert Path(result.path).name == "tidal-playlist.m3u"


class TwoPlaylistSession:
    def __init__(self, left_tracks, right_tracks, *, left_title="Left", right_title="Right"):
        self.left_tracks = left_tracks
        self.right_tracks = right_tracks
        self.left_title = left_title
        self.right_title = right_title

    def playlist(self, playlist_id: str):
        tracks = self.left_tracks if playlist_id == "left" else self.right_tracks
        title = self.left_title if playlist_id == "left" else self.right_title

        def listing(*, limit: int, offset: int):
            available = tracks[offset : offset + limit]
            return [
                SimpleNamespace(
                    id=item.id,
                    name=item.title,
                    artist=SimpleNamespace(id="a", name=item.artist),
                    album=None,
                    duration=item.duration_seconds,
                    explicit=item.explicit,
                    isrc=item.isrc,
                )
                for item in available
            ]

        return SimpleNamespace(
            id=playlist_id,
            name=title,
            description="",
            creator=None,
            num_tracks=len(tracks),
            duration=0,
            created=None,
            last_updated=None,
            tracks=listing,
            items=listing,
            get_tracks_count=lambda: len(tracks),
        )


def test_compare_matches_on_title_and_artist_not_on_id() -> None:
    left = [track("1", title="Shared", artist="Band")]
    right = [track("999", title="Shared", artist="Band")]
    client = TidalClient(TwoPlaylistSession(left, right))

    comparison = client.compare_playlists("left", "right", max_items=50)

    assert comparison.shared_count == 1
    assert comparison.left_only_count == 0
    assert comparison.right_only_count == 0
    entry = comparison.shared[0]
    assert entry.left_track_ids == ["1"]
    assert entry.right_track_ids == ["999"]
    assert entry.title == "Shared"


def test_compare_reports_each_side_and_is_case_insensitive() -> None:
    left = [track("1", title="Only Left", artist="A"), track("2", title="MiXeD", artist="A")]
    right = [track("9", title="mixed", artist="a"), track("8", title="Only Right", artist="B")]
    client = TidalClient(TwoPlaylistSession(left, right))

    comparison = client.compare_playlists("left", "right", max_items=50)

    assert comparison.shared_count == 1
    assert comparison.left_only_count == 1
    assert comparison.right_only_count == 1
    assert comparison.left_only[0].title == "Only Left"
    assert comparison.right_only[0].title == "Only Right"
    assert comparison.left_title == "Left"
    assert comparison.right_title == "Right"


def test_compare_count_distinct_songs_not_rows() -> None:
    left = [track("1", title="Same", artist="A"), track("2", title="Same", artist="A")]
    right = [track("9", title="Same", artist="A")]
    client = TidalClient(TwoPlaylistSession(left, right))

    comparison = client.compare_playlists("left", "right", max_items=50)

    assert comparison.shared_count == 1
    assert comparison.shared[0].left_track_ids == ["1", "2"]


def test_compare_reports_truncation_and_survives_missing_titles() -> None:
    left = [track(str(index), title=f"L{index}", artist="A") for index in range(4)]
    right: list[Track] = []
    session = TwoPlaylistSession(left, right)
    session.playlist = lambda playlist_id: _titles_unavailable(session, playlist_id)
    client = TidalClient(session)

    comparison = client.compare_playlists("left", "right", max_items=2)

    assert comparison.truncated is True
    assert comparison.left_title is None
    assert comparison.right_title is None


def _titles_unavailable(session: TwoPlaylistSession, playlist_id: str):
    node = TwoPlaylistSession.playlist(session, playlist_id)
    del node.name
    return node


def test_compare_wraps_an_unexpected_upstream_failure() -> None:
    session = TwoPlaylistSession([], [])

    def explode(_playlist_id: str):
        raise ValueError("raw upstream detail")

    session.playlist = explode
    client = TidalClient(session)

    with pytest.raises(TidalClientError) as caught:
        client.compare_playlists("left", "right", max_items=10)

    assert "raw upstream detail" not in str(caught.value)


def test_playlist_title_returns_none_when_it_cannot_be_read() -> None:
    session = TwoPlaylistSession([], [])

    def explode(_playlist_id: str):
        raise ValueError("upstream detail")

    session.playlist = explode
    client = TidalClient(session)

    assert client.playlist_title("left") is None


def test_playlist_title_falls_back_to_the_title_field() -> None:
    session = TwoPlaylistSession([], [])

    def node(_playlist_id: str):
        return SimpleNamespace(title="From Title Field")

    session.playlist = node
    client = TidalClient(session)

    assert client.playlist_title("left") == "From Title Field"
