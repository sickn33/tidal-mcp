from __future__ import annotations

import asyncio
import inspect
from pathlib import Path
from typing import Any

import pytest
from mcp import Client

from tests.fakes import FakeMusicClient
from tidal_mcp.catalog import MUTATION_TOOL_SPECS, READ_TOOL_SPECS, all_tool_names
from tidal_mcp.config import Settings
from tidal_mcp.drafts import DraftStore
from tidal_mcp.exceptions import TidalClientError
from tidal_mcp.models import AuthStatus
from tidal_mcp.runtime import Runtime
from tidal_mcp.server import create_server

EXPECTED_TOOLS = {
    "tidal_auth_status",
    "tidal_search",
    "tidal_list_favorite_tracks",
    "tidal_list_playlists",
    "tidal_get_playlist_tracks",
    "tidal_recommend_tracks",
    *(spec.name for spec in READ_TOOL_SPECS),
    *(spec.name for spec in MUTATION_TOOL_SPECS),
    "tidal_commit_action",
    "tidal_commit_create_playlist",
}


def make_runtime(
    tmp_path: Path, *, writes_enabled: bool = False
) -> tuple[Runtime, FakeMusicClient]:
    fake = FakeMusicClient()
    settings = Settings(
        data_dir=tmp_path,
        session_file=tmp_path / "session.json",
        writes_enabled=writes_enabled,
        draft_ttl_seconds=900,
    )
    runtime = Runtime(
        settings=settings,
        client_factory=lambda: fake,
        auth_status_checker=lambda: AuthStatus(
            authenticated=True,
            message="Fixture session is valid.",
            session_file=str(settings.session_file),
            user_id="fixture-user",
            username="fixture",
            login_command="tidal-auth",
        ),
        draft_store=DraftStore(settings.draft_dir, settings.draft_ttl_seconds),
    )
    return runtime, fake


async def call(
    runtime: Runtime, name: str, arguments: dict[str, Any] | None = None
) -> dict[str, Any]:
    async with Client(create_server(runtime), raise_exceptions=True) as client:
        result = await client.call_tool(name, arguments or {})
        assert result.is_error is False
        assert result.structured_content is not None
        return result.structured_content


def test_lists_exact_tools_with_schemas_and_safety_annotations(tmp_path: Path) -> None:
    runtime, _ = make_runtime(tmp_path)

    async def scenario() -> None:
        async with Client(create_server(runtime), raise_exceptions=True) as client:
            result = await client.list_tools()
            tools = {tool.name: tool for tool in result.tools}
            assert set(tools) == EXPECTED_TOOLS
            assert all(tool.output_schema for tool in tools.values())
            for name in EXPECTED_TOOLS - {
                *(spec.name for spec in MUTATION_TOOL_SPECS),
                "tidal_commit_action",
                "tidal_commit_create_playlist",
            }:
                assert tools[name].annotations is not None
                assert tools[name].annotations.read_only_hint is True
            assert tools["tidal_preview_create_playlist"].annotations.destructive_hint is False
            assert tools["tidal_commit_action"].annotations.destructive_hint is True
            assert tools["tidal_commit_create_playlist"].annotations.idempotent_hint is True

    asyncio.run(scenario())


def test_auth_status_is_structured(tmp_path: Path) -> None:
    runtime, _ = make_runtime(tmp_path)
    result = asyncio.run(call(runtime, "tidal_auth_status"))
    assert result["authenticated"] is True
    assert result["user_id"] == "fixture-user"


def test_catalog_and_library_tools_are_paginated(tmp_path: Path) -> None:
    runtime, _ = make_runtime(tmp_path)

    async def scenario() -> None:
        async with Client(create_server(runtime), raise_exceptions=True) as client:
            search = await client.call_tool(
                "tidal_search",
                {"query": "fixture", "media_types": ["tracks", "albums"], "limit": 2},
            )
            favorites = await client.call_tool(
                "tidal_list_favorite_tracks", {"limit": 2, "offset": 0}
            )
            playlists = await client.call_tool("tidal_list_playlists", {"limit": 10})
            playlist_tracks = await client.call_tool(
                "tidal_get_playlist_tracks",
                {"playlist_id": "playlist-1", "limit": 2},
            )

            assert search.structured_content["tracks"][0]["title"] == "Glass Harbor"
            assert search.structured_content["albums"][0]["title"] == "Fixture Album"
            assert favorites.structured_content["has_more"] is True
            assert favorites.structured_content["next_offset"] == 2
            assert playlists.structured_content["items"][0]["id"] == "playlist-1"
            assert playlist_tracks.structured_content["count"] == 2

    asyncio.run(scenario())


def test_recommendations_deduplicate_sources_and_apply_filters(tmp_path: Path) -> None:
    runtime, _ = make_runtime(tmp_path)
    result = asyncio.run(
        call(
            runtime,
            "tidal_recommend_tracks",
            {
                "seed_track_ids": ["seed-1", "seed-2"],
                "filters": {
                    "release_year_min": 2020,
                    "explicit": False,
                    "max_tracks_per_artist": 1,
                },
            },
        )
    )
    assert [item["id"] for item in result["items"]] == ["t-1", "t-3"]
    assert result["items"][0]["source_seed_ids"] == ["seed-1", "seed-2"]
    assert result["candidate_count"] == 5
    assert result["filtered_out_count"] == 3


def test_preview_is_local_and_does_not_create_playlist(tmp_path: Path) -> None:
    runtime, fake = make_runtime(tmp_path)
    result = asyncio.run(
        call(
            runtime,
            "tidal_preview_create_playlist",
            {"title": "Approved Later", "description": "Test", "track_ids": ["t-1", "t-1"]},
        )
    )
    assert result["writes_enabled"] is False
    assert [item["id"] for item in result["preview"]["tracks"]] == ["t-1", "t-1"]
    assert fake.create_calls == 0
    draft_path = runtime.settings.draft_dir / f"{result['approval_token']}.json"
    assert draft_path.exists()
    assert draft_path.stat().st_mode & 0o777 == 0o600
    assert draft_path.parent.stat().st_mode & 0o777 == 0o700


def test_commit_is_disabled_by_default(tmp_path: Path) -> None:
    runtime, fake = make_runtime(tmp_path)

    async def scenario() -> None:
        async with Client(create_server(runtime), raise_exceptions=True) as client:
            preview = await client.call_tool(
                "tidal_preview_create_playlist",
                {"title": "No Write", "track_ids": ["t-1"]},
            )
            result = await client.call_tool(
                "tidal_commit_create_playlist",
                {"approval_token": preview.structured_content["approval_token"]},
            )
            assert result.is_error is True
            assert "Remote writes are disabled" in result.content[0].text

    asyncio.run(scenario())
    assert fake.create_calls == 0


def test_commit_uses_exact_draft_and_replay_is_idempotent(tmp_path: Path) -> None:
    runtime, fake = make_runtime(tmp_path, writes_enabled=True)

    async def scenario() -> None:
        async with Client(create_server(runtime), raise_exceptions=True) as client:
            preview = await client.call_tool(
                "tidal_preview_create_playlist",
                {
                    "title": "Exact Draft",
                    "description": "Approved description",
                    "track_ids": ["t-2", "t-3"],
                },
            )
            token = preview.structured_content["approval_token"]
            first = await client.call_tool(
                "tidal_commit_create_playlist", {"approval_token": token}
            )
            second = await client.call_tool(
                "tidal_commit_create_playlist", {"approval_token": token}
            )
            assert first.structured_content == second.structured_content

    asyncio.run(scenario())
    assert fake.create_calls == 1
    assert fake.last_created == (
        "Exact Draft",
        "Approved description",
        ["t-2", "t-3"],
    )


def test_invalid_commit_token_never_reaches_client(tmp_path: Path) -> None:
    runtime, fake = make_runtime(tmp_path, writes_enabled=True)

    async def scenario() -> None:
        async with Client(create_server(runtime), raise_exceptions=True) as client:
            result = await client.call_tool(
                "tidal_commit_create_playlist",
                {"approval_token": "../this-token-is-long-enough-but-invalid"},
            )
            assert result.is_error is True
            assert "Invalid approval token format" in result.content[0].text

    asyncio.run(scenario())
    assert fake.create_calls == 0


def _required_arguments(spec: object) -> dict[str, Any]:
    values: dict[str, Any] = {
        "title": "Fixture title",
        "track_ids": ["t-1"],
        "album_ids": ["album-1"],
        "artist_ids": ["artist-1"],
        "playlist_ids": ["playlist-1"],
        "mix_ids": ["mix-1"],
        "indices": [0],
        "index": 0,
        "position": 0,
        "item_trns": ["trn:playlist:playlist-1"],
        "media_ids": ["track-1"],
        "kind": "tracks",
    }
    arguments: dict[str, Any] = {}
    for parameter in spec.params:
        if parameter.default is inspect.Parameter.empty:
            arguments[parameter.name] = values.get(parameter.name, "fixture-id")
    return arguments


def test_every_declarative_tool_executes_through_typed_mcp_contract(tmp_path: Path) -> None:
    runtime, fake = make_runtime(tmp_path)

    async def scenario() -> None:
        async with Client(create_server(runtime), raise_exceptions=True) as client:
            for spec in READ_TOOL_SPECS:
                result = await client.call_tool(spec.name, _required_arguments(spec))
                assert result.is_error is False, spec.name
                assert result.structured_content["operation"] == spec.name
            for spec in MUTATION_TOOL_SPECS:
                arguments = _required_arguments(spec)
                if spec.action == "edit_playlist":
                    arguments["title"] = "Updated fixture"
                result = await client.call_tool(spec.name, arguments)
                assert result.is_error is False, spec.name
                assert result.structured_content["action"] == spec.action
                assert result.structured_content["writes_enabled"] is False

    asyncio.run(scenario())
    assert all_tool_names() == {
        *(spec.name for spec in READ_TOOL_SPECS),
        *(spec.name for spec in MUTATION_TOOL_SPECS),
    }
    assert fake.create_calls == 0


def test_generated_handlers_return_safe_tool_errors(tmp_path: Path) -> None:
    runtime, fake = make_runtime(tmp_path)

    def fail(*_args: object, **_kwargs: object) -> None:
        raise TidalClientError("safe fixture failure")

    async def scenario() -> None:
        fake.execute_read = fail
        async with Client(create_server(runtime), raise_exceptions=True) as client:
            read = await client.call_tool("tidal_get_album", {"album_id": "album-1"})
            assert read.is_error is True
            assert "safe fixture failure" in read.content[0].text

        fake.preview_mutation = fail
        async with Client(create_server(runtime), raise_exceptions=True) as client:
            preview = await client.call_tool(
                "tidal_preview_delete_playlist", {"playlist_id": "playlist-1"}
            )
            assert preview.is_error is True

    asyncio.run(scenario())


def test_edit_preview_requires_a_real_change(tmp_path: Path) -> None:
    runtime, _ = make_runtime(tmp_path)

    async def scenario() -> None:
        async with Client(create_server(runtime), raise_exceptions=True) as client:
            result = await client.call_tool(
                "tidal_preview_edit_playlist", {"playlist_id": "playlist-1"}
            )
            assert result.is_error is True
            assert "at least one" in result.content[0].text

    asyncio.run(scenario())


def test_explicit_read_handlers_convert_client_failures(tmp_path: Path) -> None:
    runtime, fake = make_runtime(tmp_path)

    def fail(*_args: object, **_kwargs: object) -> None:
        raise TidalClientError("safe fixture failure")

    async def scenario() -> None:
        cases = [
            ("search", "tidal_search", {"query": "fixture"}),
            ("list_favorite_tracks", "tidal_list_favorite_tracks", {}),
            ("list_playlists", "tidal_list_playlists", {}),
            (
                "get_playlist_tracks",
                "tidal_get_playlist_tracks",
                {"playlist_id": "playlist-1"},
            ),
            (
                "get_track_radio",
                "tidal_recommend_tracks",
                {"seed_track_ids": ["seed-1"]},
            ),
        ]
        for method_name, tool_name, arguments in cases:
            original = getattr(fake, method_name)
            setattr(fake, method_name, fail)
            async with Client(create_server(runtime), raise_exceptions=True) as client:
                result = await client.call_tool(tool_name, arguments)
                assert result.is_error is True
                assert "safe fixture failure" in result.content[0].text
            setattr(fake, method_name, original)

    asyncio.run(scenario())


def test_generic_commit_replay_action_mismatch_and_locked_states(tmp_path: Path) -> None:
    runtime, fake = make_runtime(tmp_path, writes_enabled=True)

    async def scenario() -> None:
        async with Client(create_server(runtime), raise_exceptions=True) as client:
            preview = await client.call_tool("tidal_preview_favorite_track", {"track_ids": ["t-1"]})
            token = preview.structured_content["approval_token"]
            mismatch = await client.call_tool(
                "tidal_commit_create_playlist", {"approval_token": token}
            )
            assert mismatch.is_error is True
            first = await client.call_tool("tidal_commit_action", {"approval_token": token})
            second = await client.call_tool("tidal_commit_action", {"approval_token": token})
            assert first.structured_content == second.structured_content

            for state in ("committing", "failed"):
                created = await client.call_tool(
                    "tidal_preview_favorite_album", {"album_ids": [f"album-{state}"]}
                )
                state_token = created.structured_content["approval_token"]
                record = runtime.draft_store.load_action(state_token)
                runtime.draft_store.save_action(record.model_copy(update={"state": state}))
                locked = await client.call_tool(
                    "tidal_commit_action", {"approval_token": state_token}
                )
                assert locked.is_error is True
                assert state in locked.content[0].text or "failed" in locked.content[0].text

    asyncio.run(scenario())
    assert fake.create_calls == 1


def test_ambiguous_commit_failure_is_persistently_locked(tmp_path: Path) -> None:
    runtime, fake = make_runtime(tmp_path, writes_enabled=True)

    def fail(*_args: object, **_kwargs: object) -> None:
        raise TidalClientError("uncertain")

    fake.execute_mutation = fail

    async def scenario() -> None:
        async with Client(create_server(runtime), raise_exceptions=True) as client:
            preview = await client.call_tool("tidal_preview_favorite_track", {"track_ids": ["t-1"]})
            token = preview.structured_content["approval_token"]
            result = await client.call_tool("tidal_commit_action", {"approval_token": token})
            assert result.is_error is True
            assert "locked" in result.content[0].text
            assert runtime.draft_store.load_action(token).state == "failed"

    asyncio.run(scenario())


def test_server_main_sets_quiet_logging_and_runs(monkeypatch: pytest.MonkeyPatch) -> None:
    from tidal_mcp import server as server_module

    called: list[bool] = []
    monkeypatch.setattr(server_module.mcp, "run", lambda: called.append(True))
    server_module.main()
    assert called == [True]
