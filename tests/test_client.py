from __future__ import annotations

import stat
from pathlib import Path
from types import SimpleNamespace

import pytest
import requests

from tidal_mcp import auth_cli
from tidal_mcp.client import TidalClient, _search_bucket, _sequence
from tidal_mcp.exceptions import (
    AuthenticationRequiredError,
    PartialPlaylistCreationError,
    TidalClientError,
)
from tidal_mcp.formatting import format_album, format_artist, format_playlist, format_track
from tidal_mcp.models import SearchType


def api_track(track_id: str, title: str = "Track") -> SimpleNamespace:
    artist = SimpleNamespace(id="artist-1", name="Artist")
    album = SimpleNamespace(id="album-1", name="Album", release_date="2023-03-01")
    return SimpleNamespace(
        id=track_id,
        name=title,
        artist=artist,
        album=album,
        duration=203,
        explicit=False,
        release_date="2023-03-02",
    )


def api_playlist(playlist_id: str = "playlist-1") -> SimpleNamespace:
    return SimpleNamespace(
        id=playlist_id,
        name="Playlist",
        description="Description",
        creator=SimpleNamespace(username="owner"),
        num_tracks=2,
        duration=406,
        created="2026-01-01",
        last_updated="2026-01-02",
    )


class FakeFavorites:
    def tracks(self, **_: object) -> list[SimpleNamespace]:
        return [api_track("1"), api_track("2"), api_track("3")]

    def get_tracks_count(self) -> int:
        return 3


class FakeUser:
    def __init__(self, created: SimpleNamespace | None = None) -> None:
        self.id = "user-1"
        self.username = "fixture"
        self.favorites = FakeFavorites()
        self.created = created

    def playlists(self, **_: object) -> list[SimpleNamespace]:
        return [api_playlist("p1"), api_playlist("p2")]

    def create_playlist(self, title: str, description: str) -> SimpleNamespace:
        assert self.created is not None
        self.created.name = title
        self.created.description = description
        return self.created


class FakeSession:
    def __init__(self, created: SimpleNamespace | None = None) -> None:
        self.user = FakeUser(created)
        self._created = created

    def search(self, query: str, **_: object) -> dict[str, list[SimpleNamespace]]:
        assert query == "query"
        return {
            "tracks": [api_track("1"), api_track("2")],
            "albums": [
                SimpleNamespace(
                    id="album-1",
                    name="Album",
                    artist=SimpleNamespace(id="artist-1", name="Artist"),
                    release_date="2023-03-01",
                    num_tracks=2,
                    duration=406,
                    explicit=False,
                )
            ],
            "artists": [SimpleNamespace(id="artist-1", name="Artist")],
            "playlists": [api_playlist()],
        }

    def playlist(self, playlist_id: str) -> SimpleNamespace:
        if self._created is not None and playlist_id == self._created.id:
            return self._created
        playlist = api_playlist(playlist_id)
        playlist.items = lambda **_: [api_track("1"), api_track("2"), api_track("3")]
        return playlist

    def track(self, track_id: str) -> SimpleNamespace:
        item = api_track(track_id)
        item.get_track_radio = lambda **_: [api_track("radio-1"), api_track("radio-2")]
        return item


def test_formatters_create_stable_public_urls() -> None:
    track = format_track(api_track("1"), source_seed_ids=["seed"])
    album = format_album(FakeSession().search("query")["albums"][0])
    artist = format_artist(SimpleNamespace(id="artist-1", name="Artist"))
    playlist = format_playlist(api_playlist())
    assert track.url.endswith("/track/1")
    assert track.source_seed_ids == ["seed"]
    assert album.url.endswith("/album/album-1")
    assert artist.url.endswith("/artist/artist-1")
    assert playlist.creator == "owner"


@pytest.mark.parametrize(
    ("formatter", "value"),
    [
        (format_track, SimpleNamespace(name="No ID")),
        (format_album, SimpleNamespace(name="No ID")),
        (format_artist, SimpleNamespace(name="No ID")),
        (format_playlist, SimpleNamespace(name="No ID")),
    ],
)
def test_formatters_reject_objects_without_ids(formatter: object, value: object) -> None:
    with pytest.raises(ValueError, match="without an id"):
        formatter(value)


def test_client_read_operations_convert_and_page() -> None:
    client = TidalClient(FakeSession())
    search = client.search("query", list(SearchType), limit=1, offset=0)
    favorites = client.list_favorite_tracks(limit=2, offset=0)
    playlists = client.list_playlists(limit=1, offset=0)
    tracks = client.get_playlist_tracks("playlist-1", limit=2, offset=0)
    radio = client.get_track_radio("seed", limit=2)
    resolved = client.resolve_tracks(["1", "2"])

    assert search.tracks[0].id == "1"
    assert search.albums[0].id == "album-1"
    assert search.artists[0].id == "artist-1"
    assert search.playlists[0].id == "playlist-1"
    assert search.has_more is True
    assert favorites.has_more is True
    assert playlists.items[0].id == "p1"
    assert tracks.next_offset == 2
    assert radio[0].source_seed_ids == ["seed"]
    assert [item.id for item in resolved] == ["1", "2"]


def test_upstream_error_message_is_not_exposed() -> None:
    session = FakeSession()

    def fail_search(*_: object, **__: object) -> None:
        raise RuntimeError("secret-token-from-upstream")

    session.search = fail_search
    client = TidalClient(session)
    with pytest.raises(TidalClientError) as caught:
        client.search("query", [SearchType.TRACKS], limit=1, offset=0)
    assert "secret-token-from-upstream" not in str(caught.value)
    assert "could not search" in str(caught.value)


def test_create_playlist_reports_success() -> None:
    created = api_playlist("created")
    created.add = lambda ids: list(range(len(ids)))
    client = TidalClient(FakeSession(created))
    result = client.create_playlist("New", "Description", ["1", "2"])
    assert result.status == "success"
    assert result.playlist.title == "New"
    assert result.tracks_added == 2


def test_partial_creation_is_explicit_and_not_silently_retried() -> None:
    created = api_playlist("created")

    def fail_add(_: object) -> None:
        raise RuntimeError("fixture add failure")

    created.add = fail_add
    client = TidalClient(FakeSession(created))
    with pytest.raises(PartialPlaylistCreationError) as caught:
        client.create_playlist("New", "Description", ["1"])
    assert caught.value.result.status == "partial"
    assert caught.value.result.playlist.id == "created"


def test_missing_session_returns_safe_status(tmp_path: Path) -> None:
    session_path = tmp_path / "missing.json"
    status = TidalClient.authentication_status(session_path, "tidal-auth")
    assert status.authenticated is False
    assert status.session_file == str(session_path)
    with pytest.raises(AuthenticationRequiredError, match="No TIDAL session"):
        TidalClient.from_session_file(session_path)


def test_from_session_file_validates_login(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    session_path = tmp_path / "session.json"
    session_path.write_text("fixture", encoding="utf-8")
    session = SimpleNamespace(
        user=SimpleNamespace(id="user-1", username="fixture"),
        load_session_from_file=lambda path: None,
        check_login=lambda: True,
    )
    monkeypatch.setattr("tidal_mcp.client.tidalapi.Session", lambda: session)
    client = TidalClient.from_session_file(session_path)
    assert client.session is session


def test_session_network_failure_is_not_reported_as_expiry(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    session_path = tmp_path / "session.json"
    session_path.write_text("fixture", encoding="utf-8")

    def fail_validation() -> bool:
        raise OSError("network unavailable")

    session = SimpleNamespace(
        load_session_from_file=lambda path: None,
        check_login=fail_validation,
    )
    monkeypatch.setattr("tidal_mcp.client.tidalapi.Session", lambda: session)
    status = TidalClient.authentication_status(session_path, "tidal-auth")
    assert status.authenticated is False
    assert "Check network access" in status.message
    assert "expired" in status.message
    assert "Run `tidal-auth` again" not in status.message


def test_secure_session_save_is_atomic_and_private(tmp_path: Path) -> None:
    destination = tmp_path / "private" / "session.json"

    class SavableSession:
        def save_session_to_file(self, path: Path) -> None:
            path.write_text("secret fixture", encoding="utf-8")

    auth_cli._save_session_securely(SavableSession(), destination)
    assert destination.read_text(encoding="utf-8") == "secret fixture"
    assert stat.S_IMODE(destination.parent.stat().st_mode) == 0o700
    assert stat.S_IMODE(destination.stat().st_mode) == 0o600


def test_authorization_url_is_normalized() -> None:
    assert (
        auth_cli._authorization_url(SimpleNamespace(verification_uri_complete="login.tidal.com/x"))
        == "https://login.tidal.com/x"
    )


def test_sequence_and_search_bucket_defensive_shapes() -> None:
    assert _sequence(None) == []
    assert _sequence((1, 2)) == [1, 2]
    assert _sequence(3) == []
    assert _search_bucket(SimpleNamespace(tracks=SimpleNamespace(items=[1])), "tracks") == [1]
    assert _search_bucket({"tracks": {"items": [2]}}, "tracks") == [2]


@pytest.mark.parametrize(
    ("load_error", "authenticated"), [(RuntimeError("bad"), True), (None, False)]
)
def test_session_file_rejects_unreadable_or_expired_sessions(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    load_error: Exception | None,
    authenticated: bool,
) -> None:
    session_path = tmp_path / "session.json"
    session_path.write_text("fixture", encoding="utf-8")

    def load(_path: Path) -> None:
        if load_error:
            raise load_error

    session = SimpleNamespace(load_session_from_file=load, check_login=lambda: authenticated)
    monkeypatch.setattr("tidal_mcp.client.tidalapi.Session", lambda: session)
    with pytest.raises(AuthenticationRequiredError):
        TidalClient.from_session_file(session_path)


def test_session_network_failure_during_load_is_not_reported_as_corruption(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    session_path = tmp_path / "session.json"
    session_path.write_text("fixture", encoding="utf-8")
    session = SimpleNamespace(
        load_session_from_file=lambda _path: (_ for _ in ()).throw(
            requests.ConnectionError("offline")
        )
    )
    monkeypatch.setattr("tidal_mcp.client.tidalapi.Session", lambda: session)
    with pytest.raises(TidalClientError, match="network request failed"):
        TidalClient.from_session_file(session_path)


def test_authentication_status_reports_valid_user_without_username(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    session_path = tmp_path / "session.json"
    session_path.write_text("fixture", encoding="utf-8")
    session = SimpleNamespace(
        user=SimpleNamespace(id="user-1", username=None),
        load_session_from_file=lambda _path: None,
        check_login=lambda: True,
    )
    monkeypatch.setattr("tidal_mcp.client.tidalapi.Session", lambda: session)
    status = TidalClient.authentication_status(session_path, "tidal-auth")
    assert status.authenticated is True
    assert status.username is None


def test_legacy_read_fallbacks_and_safe_failures() -> None:
    session = FakeSession()

    def legacy_tracks(**kwargs: object) -> list[SimpleNamespace]:
        if not isinstance(kwargs["order"], str):
            raise TypeError
        return [api_track("1")]

    session.user.favorites.tracks = legacy_tracks

    original_playlists = session.user.playlists

    def legacy_playlists(**kwargs: object) -> list[SimpleNamespace]:
        if kwargs:
            raise TypeError
        return original_playlists()

    session.user.playlists = legacy_playlists
    playlist = session.playlist("playlist-1")
    session.playlist = lambda _playlist_id: playlist
    client = TidalClient(session)
    assert client.list_favorite_tracks(1, 0).count == 1
    assert client.list_playlists(1, 0).count == 1
    assert client.get_playlist_tracks("playlist-1", 1, 0).count == 1

    for method_name, call in (
        ("tracks", lambda: client.list_favorite_tracks(1, 0)),
        ("playlists", lambda: client.list_playlists(1, 0)),
    ):
        setattr(
            session.user.favorites if method_name == "tracks" else session.user, method_name, None
        )
        with pytest.raises(TidalClientError):
            call()

    session.playlist = lambda _playlist_id: (_ for _ in ()).throw(RuntimeError("private"))
    with pytest.raises(TidalClientError):
        client.get_playlist_tracks("playlist-1", 1, 0)


def test_track_helpers_convert_upstream_errors() -> None:
    session = FakeSession()
    session.track = lambda _track_id: (_ for _ in ()).throw(RuntimeError("private"))
    client = TidalClient(session)
    with pytest.raises(TidalClientError):
        client.get_track_radio("1", 1)
    with pytest.raises(TidalClientError):
        client.resolve_tracks(["1"])


def test_create_playlist_covers_result_shapes_and_refresh_failure() -> None:
    created = api_playlist("created")
    session = FakeSession(created)
    client = TidalClient(session)

    created.add = lambda _ids: False
    result = client.create_playlist("New", "Description", ["1"])
    assert result.status == "partial"
    assert result.tracks_added == 0

    created.add = lambda _ids: True
    session.playlist = lambda _playlist_id: (_ for _ in ()).throw(RuntimeError("refresh"))
    result = client.create_playlist("New", "Description", ["1"])
    assert result.tracks_added == 1

    result = client.create_playlist("Empty", "Description", [])
    assert result.tracks_added == 0


def test_create_playlist_failure_is_wrapped() -> None:
    session = FakeSession()
    client = TidalClient(session)
    with pytest.raises(TidalClientError):
        client.create_playlist("New", "Description", ["1"])


def test_extended_adapter_wraps_read_preview_and_write_failures() -> None:
    session = FakeSession()
    client = TidalClient(session)
    session.album = lambda _album_id: (_ for _ in ()).throw(RuntimeError("private"))
    with pytest.raises(TidalClientError):
        client.execute_read("tidal_get_album", {"album_id": "1"})

    session.playlist = lambda _playlist_id: (_ for _ in ()).throw(RuntimeError("private"))
    with pytest.raises(TidalClientError):
        client.preview_mutation("delete_playlist", {"playlist_id": "1"})
    with pytest.raises(TidalClientError):
        client.execute_mutation("delete_playlist", {"playlist_id": "1"})


def short_favorites_session(page_items: int, count: object = None) -> SimpleNamespace:
    favorites = SimpleNamespace(
        tracks=lambda **_: [api_track(str(index)) for index in range(page_items)]
    )
    if count is not None:
        favorites.get_tracks_count = count
    return SimpleNamespace(user=SimpleNamespace(favorites=favorites))


def test_favorites_short_pages_still_report_more_from_collection_total() -> None:
    client = TidalClient(short_favorites_session(2, lambda: 657))

    first = client.list_favorite_tracks(limit=3, offset=0)
    assert [item.id for item in first.items] == ["0", "1"]
    assert first.count == 2
    assert first.has_more is True
    assert first.next_offset == 3

    middle = client.list_favorite_tracks(limit=3, offset=300)
    assert middle.has_more is True
    assert middle.next_offset == 303

    tail = client.list_favorite_tracks(limit=3, offset=654)
    assert tail.has_more is False
    assert tail.next_offset is None


def test_favorites_without_usable_count_fall_back_to_length_sentinel() -> None:
    def failing_count() -> int:
        raise RuntimeError("count unavailable")

    failing = TidalClient(short_favorites_session(2, failing_count))
    short_page = failing.list_favorite_tracks(limit=3, offset=0)
    assert short_page.count == 2
    assert short_page.has_more is False
    assert short_page.next_offset is None

    countless = TidalClient(short_favorites_session(4))
    full_page = countless.list_favorite_tracks(limit=3, offset=0)
    assert full_page.count == 3
    assert full_page.has_more is True
    assert full_page.next_offset == 3
