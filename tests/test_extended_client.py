from __future__ import annotations

import inspect
from types import SimpleNamespace
from typing import Any

import pytest
import tidalapi.types as tidal_types

from tidal_mcp.catalog import MUTATION_TOOL_SPECS, READ_TOOL_SPECS
from tidal_mcp.client import TidalClient
from tidal_mcp.exceptions import PartialPlaylistCreationError, TidalClientError
from tidal_mcp.models import CommitPlaylistResult, Playlist


class Node:
    def __init__(self, identifier: str = "node-1", *, path: str = "rock") -> None:
        self.id = identifier
        self.name = "Fixture node"
        self.title = "Fixture node"
        self.description = "Fixture description"
        self.path = path
        self.num_tracks = 1
        self.duration = 180
        self.creator = SimpleNamespace(username="fixture")
        self.created = "2026-01-01"
        self.last_updated = "2026-01-02"

    def __getattr__(self, name: str) -> Any:
        if name in {
            "get_url",
            "image",
            "wide_image",
            "video",
        }:
            return lambda *_args, **_kwargs: "https://fixture.invalid/value"
        if name in {"review", "get_bio"}:
            return lambda *_args, **_kwargs: "Fixture editorial text"
        if name in {"get_tracks_count", "get_items_count"}:
            return lambda *_args, **_kwargs: 2
        if name == "get_audio_resolution":
            return lambda *_args, **_kwargs: [[24, 96000]]
        if name in {
            "tracks",
            "items",
            "similar",
            "get_albums",
            "get_albums_ep_singles",
            "get_albums_other",
            "get_radio",
            "get_similar",
            "get_top_tracks",
            "get_videos",
            "get_track_radio",
        }:
            return lambda *_args, **_kwargs: [Node("result-1"), Node("result-2")]
        if name in {"get_radio_mix", "lyrics", "get_stream", "page"}:
            return lambda *_args, **_kwargs: Node("result-1")
        if name in {
            "add",
            "add_by_isrc",
            "clear",
            "delete",
            "edit",
            "merge",
            "move_by_id",
            "move_by_index",
            "move_by_indices",
            "remove_by_id",
            "remove_by_index",
            "remove_by_indices",
            "delete_by_id",
            "set_playlist_public",
            "set_playlist_private",
            "rename",
            "remove",
            "add_items",
            "move_items_to_folder",
            "move_items_to_root",
        }:
            return lambda *_args, **_kwargs: True
        raise AttributeError(name)


class GenreNode(Node):
    def items(self, _model: object) -> list[Node]:
        return [Node("genre-result-1"), Node("genre-result-2")]


class UniversalFavorites(Node):
    def get_genres(self) -> list[GenreNode]:
        return [GenreNode(path="rock")]

    def __getattr__(self, name: str) -> Any:
        if name.startswith(("add_", "remove_")):
            return lambda *_args, **_kwargs: True
        if name.startswith("get_") and name.endswith("_count"):
            return lambda: 2
        if name in {"albums", "artists", "playlists", "videos", "mixes", "playlist_folders"}:
            return lambda *_args, **_kwargs: [Node("favorite-1"), Node("favorite-2")]
        return super().__getattr__(name)


class UniversalUser(Node):
    def __init__(self) -> None:
        super().__init__("user-1")
        self.favorites = UniversalFavorites()

    def playlists(self, *_args: object, **_kwargs: object) -> list[Node]:
        return [Node("playlist-1")]

    def public_playlists(self, **_kwargs: object) -> list[Node]:
        return [Node("playlist-1"), Node("playlist-2")]

    def playlist_and_favorite_playlists(self, **_kwargs: object) -> list[Node]:
        return [Node("playlist-1"), Node("playlist-2")]

    def create_playlist(self, title: str, description: str, parent_id: str = "root") -> Node:
        item = Node("created-playlist")
        item.name = title
        item.description = description
        item.parent_id = parent_id
        return item

    def create_folder(self, title: str, parent_id: str = "root") -> Node:
        item = Node("created-folder")
        item.name = title
        item.parent_id = parent_id
        return item


class UniversalSession(Node):
    def __init__(self) -> None:
        super().__init__("session")
        self.user = UniversalUser()
        self.genre = UniversalFavorites()

    def track(self, track_id: str, **_kwargs: object) -> Node:
        return Node(track_id)

    def album(self, album_id: str) -> Node:
        return Node(album_id)

    def artist(self, artist_id: str) -> Node:
        return Node(artist_id)

    def playlist(self, playlist_id: str) -> Node:
        return Node(playlist_id)

    def video(self, video_id: str) -> Node:
        return Node(video_id)

    def mix(self, mix_id: str) -> Node:
        return Node(mix_id)

    def mixv2(self, mix_id: str) -> Node:
        return Node(mix_id)

    def folder(self, folder_id: str) -> Node:
        return Node(folder_id)

    def get_user(self, user_id: int | None) -> Node:
        return Node(str(user_id or "user-1"))

    def get_albums_by_barcode(self, _barcode: str) -> list[Node]:
        return [Node("album-1"), Node("album-2")]

    def get_tracks_by_isrc(self, _isrc: str) -> list[Node]:
        return [Node("track-1"), Node("track-2")]

    def __getattr__(self, name: str) -> Any:
        if name in {
            "home",
            "explore",
            "for_you",
            "genres",
            "hires_page",
            "local_genres",
            "mixes",
            "moods",
            "videos",
        }:
            return lambda: Node(name)
        return super().__getattr__(name)


def arguments(spec: object) -> dict[str, Any]:
    values: dict[str, Any] = {
        "title": "Fixture title",
        "track_ids": ["track-1"],
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
        "genre_path": "rock",
    }
    result: dict[str, Any] = {}
    for parameter in spec.params:
        if parameter.default is inspect.Parameter.empty:
            result[parameter.name] = values.get(parameter.name, "fixture-id")
        else:
            result[parameter.name] = parameter.default
    if getattr(spec, "action", None) == "edit_playlist":
        result["title"] = "Updated title"
    return result


def test_every_read_plan_executes_against_the_tidalapi_adapter() -> None:
    client = TidalClient(UniversalSession())
    for spec in READ_TOOL_SPECS:
        result = client.execute_read(spec.name, arguments(spec))
        assert result.operation == spec.name


def test_every_mutation_plan_executes_against_the_tidalapi_adapter() -> None:
    client = TidalClient(UniversalSession())
    for spec in MUTATION_TOOL_SPECS:
        payload = arguments(spec)
        preview = client.preview_mutation(spec.action, payload)
        result = client.execute_mutation(spec.action, payload)
        assert preview["action"] == spec.action
        assert result.action == spec.action
        assert result.status == "success"


def test_adapter_rejects_unknown_operations_without_leaking_details() -> None:
    client = TidalClient(UniversalSession())
    assert client._enum_value(tidal_types.ItemOrder, "DATE") is tidal_types.ItemOrder.Date
    with pytest.raises(TidalClientError, match="Unsupported read operation"):
        client.execute_read("tidal_unknown", {})
    with pytest.raises(TidalClientError, match="Unsupported mutation action"):
        client.execute_mutation("unknown", {})


def test_create_playlist_action_adds_nonempty_track_list() -> None:
    client = TidalClient(UniversalSession())
    result = client.execute_mutation(
        "create_playlist",
        {
            "title": "Fixture",
            "description": "",
            "parent_folder_id": "root",
            "track_ids": ["track-1"],
        },
    )
    assert result.details["tracks_added"] == 1


def test_mutation_partial_playlist_result_is_preserved(monkeypatch: pytest.MonkeyPatch) -> None:
    client = TidalClient(UniversalSession())
    playlist = Playlist(id="partial", title="Partial", url="https://tidal.com/partial")
    old_result = CommitPlaylistResult(
        status="partial",
        message="Only one track was added.",
        playlist=playlist,
        tracks_requested=2,
        tracks_added=1,
        warning="Inspect the playlist.",
    )

    def fail(_payload: dict[str, Any]) -> CommitPlaylistResult:
        raise PartialPlaylistCreationError(old_result)

    monkeypatch.setattr(client, "_create_playlist_action", fail)
    result = client.execute_mutation(
        "create_playlist",
        {
            "title": "Partial",
            "description": "",
            "parent_folder_id": "root",
            "track_ids": ["1", "2"],
        },
    )
    assert result.status == "partial"
    assert result.details == {"tracks_requested": 2, "tracks_added": 1}
