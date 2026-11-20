from __future__ import annotations

import asyncio
import threading
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock
from unittest.mock import call as mock_call

from mcp import Client
from tidalapi.exceptions import MetadataNotAvailable

from tests.fakes import FakeMusicClient
from tests.test_client import api_track
from tests.test_server import call, make_runtime
from tidal_mcp.client import TidalClient
from tidal_mcp.server import create_server


def test_saved_search_walks_empty_and_partial_windows_in_source_order(tmp_path: Path) -> None:
    def read(*, limit, offset, **order):
        assert order["order"].value == "DATE"
        assert order["order_direction"].value == "DESC"
        visible = {50: "Déjà Vu", 51: "Halo", 100: "Déjà Vu (Live)", 105: "Déjà Vu"}
        page = []
        for index, title in visible.items():
            if offset <= index < offset + limit:
                track = api_track(str(index), title)
                track.artist.name = "Beyoncé"
                track.album.name = "Festival"
                page.append(track)
        return page

    favorites = Mock()
    favorites.get_tracks_count.return_value = 106
    favorites.tracks.side_effect = read
    adapter = TidalClient(SimpleNamespace(user=SimpleNamespace(favorites=favorites)))
    runtime, _ = make_runtime(tmp_path)
    runtime.client_factory = lambda: adapter

    async def scenario():
        query = {"query": "BEYONCE deja festival"}
        async with Client(create_server(runtime)) as client:

            async def window(offset, limit):
                response = await client.call_tool(
                    "tidal_search_favorite_tracks", {**query, "scan_limit": limit, "offset": offset}
                )
                assert not response.is_error
                return response.structured_content

            empty = await window(0, 50)
            assert empty["count"] == empty["scanned_count"] == 0
            assert empty["has_more"] and empty["next_offset"] == 50
            middle = await window(empty["next_offset"], 52)
            assert middle["scanned_count"] == 3
            assert [t["id"] for t in middle["items"]] == ["50", "100"]
            assert middle["has_more"] and middle["next_offset"] == 102
            tail = await window(middle["next_offset"], 50)
            assert [t["id"] for t in tail["items"]] == ["105"]
            assert not tail["has_more"] and tail["next_offset"] is None
            past_end = await window(200, 20)
            assert past_end["items"] == [] and past_end["next_offset"] is None

    asyncio.run(scenario())
    assert favorites.get_tracks_count.call_count == 4
    assert [(c.kwargs["limit"], c.kwargs["offset"]) for c in favorites.tracks.call_args_list] == [
        (50, 0),
        (50, 50),
        (2, 100),
        (50, 102),
        (20, 200),
    ]


def test_counted_favorite_listing_does_not_repeat_a_lookahead_after_a_hidden_row() -> None:
    def read(*, limit, offset, **_):
        return [api_track(str(i)) for i in range(offset, offset + limit) if 0 < i < 7]

    favorites = SimpleNamespace(tracks=read, get_tracks_count=lambda: 7)
    adapter = TidalClient(SimpleNamespace(user=SimpleNamespace(favorites=favorites)))
    ids = [t.id for offset in (0, 3, 6) for t in adapter.list_favorite_tracks(3, offset).items]
    assert ids == ["1", "2", "3", "4", "5", "6"]


def test_favorite_search_handles_an_underreported_total_across_internal_pages() -> None:
    favorites = Mock()
    favorites.get_tracks_count.return_value = 20
    favorites.tracks.side_effect = lambda limit, offset, **_: [
        api_track(str(i)) for i in range(offset, min(102, offset + limit))
    ]
    adapter = TidalClient(SimpleNamespace(user=SimpleNamespace(favorites=favorites)))
    first = adapter.favorite_track_window(100, 0)
    assert first.count == 100 and first.next_offset == 100
    last = adapter.favorite_track_window(2, first.next_offset)
    assert [item.id for item in last.items] == ["100", "101"]
    assert not last.has_more and last.next_offset is None


def test_saved_search_errors_and_schema_limits(tmp_path: Path) -> None:
    favorites = Mock()
    favorites.get_tracks_count.side_effect = RuntimeError("private-provider-detail")
    runtime, _ = make_runtime(tmp_path)
    runtime.client_factory = lambda: TidalClient(
        SimpleNamespace(user=SimpleNamespace(favorites=favorites))
    )

    async def scenario():
        async with Client(create_server(runtime)) as client:
            for arguments in (
                {"query": " "},
                {"query": "a", "scan_limit": 501},
                {"query": "a", "offset": -1},
            ):
                assert (await client.call_tool("tidal_search_favorite_tracks", arguments)).is_error
            favorites.get_tracks_count.assert_not_called()
            result = await client.call_tool("tidal_search_favorite_tracks", {"query": "a"})
            assert result.is_error and "scan favorite tracks" in result.content[0].text
            assert "private-provider-detail" not in result.content[0].text

    asyncio.run(scenario())


def test_playlist_radio_matches_recordings_and_preserves_eligible_editions(tmp_path: Path) -> None:
    def recording(identifier, code=None, *, explicit=False):
        item = api_track(identifier, "Same Title")
        item.isrc = code
        item.explicit = explicit
        return item

    existing = [recording("a", "us-aaa-24-00001"), recording("a"), recording("b"), recording("c")]
    playlist = Mock()
    playlist.get_tracks_count.return_value = len(existing)
    playlist.tracks.return_value = existing
    good = recording("clean", "USAAA2400002")
    first = [
        recording("b"),
        recording("reissue", "USAAA2400001"),
        recording("explicit", "us-aaa-24-00002", explicit=True),
        good,
        recording("repeated-recording", "us-aaa-24-00002"),
        recording("other", "not an ISRC"),
    ]
    second = [good, recording("other-2", "not an ISRC"), recording("manually-excluded")]
    radios = {"a": first, "c": second}
    session = Mock()
    session.playlist.return_value = playlist
    session.track.side_effect = lambda seed: SimpleNamespace(
        get_track_radio=lambda **_: radios[seed]
    )
    runtime, _ = make_runtime(tmp_path)
    runtime.client_factory = lambda: TidalClient(session)
    result = asyncio.run(
        call(
            runtime,
            "tidal_recommend_for_playlist",
            {
                "playlist_id": "playlist",
                "seed_count": 2,
                "filters": {
                    "explicit": False,
                    "max_tracks_per_artist": 3,
                    "exclude_track_ids": ["manually-excluded"],
                },
            },
        )
    )
    assert result["playlist_tracks_checked"] == 4
    assert result["seed_track_ids"] == ["a", "c"]
    assert result["unavailable_seed_ids"] == []
    assert result["candidate_count"] == 8 and result["already_in_playlist_count"] == 2
    assert [t["id"] for t in result["items"]] == ["clean", "other", "other-2"]
    assert result["items"][0]["source_seed_ids"] == ["a", "c"]
    assert result["filtered_out_count"] == 5 and result["returned_count"] == 3
    session.playlist.assert_called_once_with("playlist")
    playlist.get_tracks_count.assert_called_once_with()
    playlist.tracks.assert_called_once_with(limit=4, offset=0)
    assert session.track.call_args_list == [mock_call("a"), mock_call("c")]


def test_radio_skips_only_missing_stations_and_limits_provider_results(tmp_path: Path) -> None:
    playlist = Mock()
    playlist.get_tracks_count.return_value = 2
    playlist.tracks.return_value = [api_track("a"), api_track("b")]
    radio = Mock(side_effect=MetadataNotAvailable("upstream details"))
    session = Mock()
    session.playlist.return_value = playlist
    session.track.side_effect = lambda seed: SimpleNamespace(
        get_track_radio=radio if seed == "a" else lambda **_: [api_track("new"), api_track("extra")]
    )
    runtime, _ = make_runtime(tmp_path)
    runtime.client_factory = lambda: TidalClient(session)
    args = {"playlist_id": "p", "limit_per_seed": 1}

    async def scenario():
        async with Client(create_server(runtime)) as client:
            response = await client.call_tool("tidal_recommend_for_playlist", args)
            assert not response.is_error
            result = response.structured_content
            assert result["unavailable_seed_ids"] == ["a"]
            assert [t["id"] for t in result["items"]] == ["new"]
            one = await client.call_tool("tidal_recommend_for_playlist", {**args, "seed_count": 1})
            assert one.structured_content["items"] == []
            assert one.structured_content["unavailable_seed_ids"] == ["a"]
            manual = await client.call_tool("tidal_recommend_tracks", {"seed_track_ids": ["a"]})
            assert manual.is_error and "no Track Radio" in manual.content[0].text
            radio.side_effect = RuntimeError("private-provider-detail")
            error = await client.call_tool("tidal_recommend_for_playlist", args)
            assert error.is_error and "private-provider-detail" not in error.content[0].text

    asyncio.run(scenario())


def test_recommendation_scan_checks_full_budget_before_reading_tracks_or_radio(
    tmp_path: Path,
) -> None:
    playlist = Mock()
    session = Mock()
    session.playlist.return_value = playlist
    runtime, _ = make_runtime(tmp_path)
    runtime.client_factory = lambda: TidalClient(session)

    async def scenario():
        async with Client(create_server(runtime)) as client:

            async def recommend():
                return await client.call_tool(
                    "tidal_recommend_for_playlist", {"playlist_id": "p", "max_playlist_tracks": 51}
                )

            playlist.get_tracks_count.return_value = 52
            over = await recommend()
            assert over.is_error and "52" in over.content[0].text
            playlist.tracks.assert_not_called()
            playlist.get_tracks_count.return_value = 0
            empty = await recommend()
            assert (
                empty.structured_content["seed_track_ids"]
                == empty.structured_content["items"]
                == []
            )
            playlist.tracks.assert_not_called()
            session.track.assert_not_called()
            playlist.get_tracks_count.return_value = 51
            playlist.tracks.side_effect = [[], [api_track("last")]]
            session.track.return_value.get_track_radio.return_value = []
            sparse = await recommend()
            assert sparse.structured_content["seed_track_ids"] == ["last"]
            assert playlist.tracks.call_args_list == [
                mock_call(limit=50, offset=0),
                mock_call(limit=1, offset=50),
            ]
            playlist.get_tracks_count.side_effect = RuntimeError("private-count-error")
            error = await recommend()
            assert error.is_error and "private-count-error" not in error.content[0].text
            session.track.assert_called_once_with("last")

    asyncio.run(scenario())


def test_manual_radio_accepts_200_exclusions_plus_seeds_and_fetches_each_seed_once(
    tmp_path: Path,
) -> None:
    runtime, fake = make_runtime(tmp_path)
    fake.get_track_radio = Mock(wraps=fake.get_track_radio)
    excluded = [f"skip-{i}" for i in range(200)]
    seeds = ["seed-1", "seed-2", *[f"s{i}" for i in range(8)]]
    args = {"seed_track_ids": seeds, "filters": {"exclude_track_ids": excluded}}
    result = asyncio.run(call(runtime, "tidal_recommend_tracks", args))
    assert result["filters"]["exclude_track_ids"] == [*excluded, *seeds]
    assert result["returned_count"] == 5
    fake.get_track_radio.reset_mock()
    asyncio.run(call(runtime, "tidal_recommend_tracks", {**args, "seed_track_ids": ["seed-1"] * 2}))
    fake.get_track_radio.assert_called_once_with("seed-1", 10)


def test_simultaneous_first_reads_share_session_and_keep_event_loop_available(
    tmp_path: Path,
) -> None:
    runtime, fake = make_runtime(tmp_path)
    threads = []
    release = threading.Event()

    async def scenario():
        loop = asyncio.get_running_loop()
        started = asyncio.Event()

        def connect() -> FakeMusicClient:
            threads.append(threading.get_ident())
            loop.call_soon_threadsafe(started.set)
            assert release.wait(timeout=5)
            return fake

        runtime.client_factory = connect
        async with Client(create_server(runtime)) as client:
            async with asyncio.TaskGroup() as tasks:
                favorites = tasks.create_task(client.call_tool("tidal_list_favorite_tracks", {}))
                playlist = tasks.create_task(
                    client.call_tool("tidal_get_playlist", {"playlist_id": "p"})
                )
                try:
                    await asyncio.wait_for(started.wait(), timeout=3)
                    status = await asyncio.wait_for(
                        client.call_tool("tidal_auth_status", {}), timeout=3
                    )
                    assert status.structured_content["authenticated"]
                finally:
                    release.set()
            assert not favorites.result().is_error and not playlist.result().is_error

    asyncio.run(scenario())
    assert len(threads) == 1 and threads[0] != threading.get_ident()
