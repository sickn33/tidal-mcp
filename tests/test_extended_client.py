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


def tidalapi_named(class_name: str):
    """Build a fixture whose class name matches the real tidalapi class.

    Both the client and the formatter dispatch on `type(item).__name__`, so a fixture only
    exercises the real branch when it carries the upstream class name.
    """

    def get(self: Node) -> Node:
        return Node("resolved-page-item")

    return type(class_name, (Node,), {"get": get})


PageItemNode = tidalapi_named("PageItem")


class CategoryNode(Node):
    def __init__(self, *, with_more: bool = True) -> None:
        super().__init__("category-1")
        self.items = [PageItemNode("page-item-1"), Node("concrete-1")]
        self._more = SimpleNamespace(api_path="pages/more") if with_more else None


class EditorialPageNode(Node):
    def __init__(self, identifier: str = "page-1", *, with_more: bool = True) -> None:
        super().__init__(identifier)
        self.title = "Fixture editorial page"
        self.categories = [CategoryNode(with_more=with_more)]


PageLinkNode = tidalapi_named("PageLink")


def linked_page(identifier: str = "linked-page") -> Node:
    """A fixture whose class name matches tidalapi's Page, so it serialises as a page."""
    page = tidalapi_named("Page")(identifier)
    page.title = "Fixture editorial page"
    page.categories = []
    return page


def link_list_page() -> EditorialPageNode:
    page = EditorialPageNode("link-list")
    link = PageLinkNode("page-link-1")
    link.title = "Fixture link"
    link.api_path = "pages/rock"
    link.get = linked_page
    category = Node("link-category")
    category.items = [link]
    page.categories = [category]
    return page


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
        self.page = SimpleNamespace(get=lambda api_path: EditorialPageNode(api_path))

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
            return lambda: EditorialPageNode(name)
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
        "page": "home",
        "category_index": 0,
        "link_index": 0,
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


def test_editorial_navigation_rejects_out_of_range_targets() -> None:
    session = UniversalSession()
    client = TidalClient(session)

    with pytest.raises(TidalClientError, match="no category at index 9"):
        client.execute_read(
            "tidal_list_page_category_items",
            {"page": "home", "category_index": 9, "limit": 2, "offset": 0},
        )

    session.home = lambda: EditorialPageNode("home", with_more=False)
    with pytest.raises(TidalClientError, match="has no further items"):
        client.execute_read(
            "tidal_show_more_page_category",
            {"page": "home", "category_index": 0},
        )

    session.home = lambda: link_list_page()
    with pytest.raises(TidalClientError, match="no link at index 4"):
        client.execute_read(
            "tidal_open_page_link",
            {"page": "home", "category_index": 0, "link_index": 4},
        )


def test_editorial_browse_rejects_an_unknown_page() -> None:
    session = UniversalSession()
    client = TidalClient(session)

    with pytest.raises(TidalClientError, match="Unsupported editorial page"):
        client.execute_read(
            "tidal_list_page_category_items",
            {"page": "unknown", "category_index": 0, "limit": 2, "offset": 0},
        )


def test_page_category_items_resolve_lazy_items_and_skip_empty_categories() -> None:
    session = UniversalSession()
    page = Node("home")
    page.categories = [None, CategoryNode(with_more=False)]
    session.home = lambda: page
    client = TidalClient(session)

    items = client.execute_read(
        "tidal_list_page_category_items",
        {"page": "home", "category_index": 0, "limit": 5, "offset": 0},
    )
    assert [item.id for item in items.items] == ["resolved-page-item", "concrete-1"]

    with pytest.raises(TidalClientError, match="has no further items"):
        client.execute_read(
            "tidal_show_more_page_category",
            {"page": "home", "category_index": 0},
        )


def test_page_links_are_paged_and_openable() -> None:
    session = UniversalSession()
    session.home = lambda: link_list_page()
    client = TidalClient(session)

    links = client.execute_read(
        "tidal_list_page_links",
        {"page": "home", "category_index": 0, "limit": 10, "offset": 0},
    )
    assert [item.id for item in links.items] == ["pages/rock"]
    assert links.items[0].type == "page_link"

    opened = client.execute_read(
        "tidal_open_page_link",
        {"page": "home", "category_index": 0, "link_index": 0},
    )
    assert opened.item.title == "Fixture editorial page"


def test_mix_v2_items_resolve_lazy_wrappers() -> None:
    session = UniversalSession()
    mix = Node("mix-v2-1")
    mix._items = [PageItemNode("page-item"), Node("concrete-track")]
    session.mixv2 = lambda _identifier: mix
    client = TidalClient(session)

    page = client.execute_read(
        "tidal_get_mix_v2_items",
        {"mix_id": "mix-v2-1", "limit": 1, "offset": 0},
    )
    assert [item.id for item in page.items] == ["resolved-page-item"]
    assert page.limit == 1


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


def favorites_listing_session(page_items: int, **counters: Any) -> SimpleNamespace:
    def listing(**_kwargs: Any) -> list[SimpleNamespace]:
        return [SimpleNamespace(id=str(index)) for index in range(page_items)]

    favorites = SimpleNamespace(
        albums=listing,
        artists=listing,
        playlists=listing,
        videos=listing,
        mixes=listing,
    )
    for name, value in counters.items():
        setattr(favorites, name, value)
    return SimpleNamespace(user=SimpleNamespace(favorites=favorites))


def listing_params(limit: int, offset: int) -> dict[str, Any]:
    return {"limit": limit, "offset": offset, "order": None, "order_direction": None}


def test_favorite_album_short_page_reports_more_from_collection_total() -> None:
    client = TidalClient(favorites_listing_session(2, get_albums_count=lambda: 657))

    first = client.execute_read("tidal_list_favorite_albums", listing_params(3, 0))
    assert [item.id for item in first.items] == ["0", "1"]
    assert first.count == 2
    assert first.limit == 3
    assert first.offset == 0
    assert first.has_more is True
    assert first.next_offset == 3

    middle = client.execute_read("tidal_list_favorite_albums", listing_params(3, 300))
    assert middle.has_more is True
    assert middle.next_offset == 303


def test_favorite_album_walk_ends_when_offset_reaches_collection_total() -> None:
    client = TidalClient(favorites_listing_session(2, get_albums_count=lambda: 657))

    tail = client.execute_read("tidal_list_favorite_albums", listing_params(3, 654))
    assert tail.count == 2
    assert tail.offset == 654
    assert tail.has_more is False
    assert tail.next_offset is None


def test_every_counted_favorite_listing_uses_its_own_collection_total() -> None:
    client = TidalClient(
        favorites_listing_session(
            2,
            get_artists_count=lambda: 40,
            get_playlists_count=lambda: 12,
            get_videos_count=lambda: 3,
        )
    )

    artists = client.execute_read("tidal_list_favorite_artists", listing_params(5, 10))
    assert artists.has_more is True
    assert artists.next_offset == 15

    playlists = client.execute_read("tidal_list_favorite_playlists", listing_params(4, 8))
    assert playlists.has_more is False
    assert playlists.next_offset is None

    videos = client.execute_read("tidal_list_favorite_videos", listing_params(2, 0))
    assert videos.has_more is True
    assert videos.next_offset == 2


def test_favorite_mixes_short_page_still_uses_the_length_sentinel() -> None:
    client = TidalClient(
        favorites_listing_session(
            2,
            get_albums_count=lambda: 657,
            get_artists_count=lambda: 657,
            get_playlists_count=lambda: 657,
            get_videos_count=lambda: 657,
        )
    )

    mixes = client.execute_read("tidal_list_favorite_mixes", listing_params(3, 0))
    assert [item.id for item in mixes.items] == ["0", "1"]
    assert mixes.count == 2
    assert mixes.has_more is False
    assert mixes.next_offset is None


def test_favorite_listings_fall_back_to_length_sentinel_without_a_usable_counter() -> None:
    def failing_count() -> int:
        raise RuntimeError("count unavailable")

    failing = TidalClient(favorites_listing_session(2, get_albums_count=failing_count))
    short_page = failing.execute_read("tidal_list_favorite_albums", listing_params(3, 0))
    assert short_page.count == 2
    assert short_page.has_more is False
    assert short_page.next_offset is None

    countless = TidalClient(favorites_listing_session(4))
    full_page = countless.execute_read("tidal_list_favorite_albums", listing_params(3, 0))
    assert full_page.count == 3
    assert full_page.has_more is True
    assert full_page.next_offset == 3


def test_empty_counted_favorite_page_keeps_the_walk_alive() -> None:
    client = TidalClient(favorites_listing_session(0, get_albums_count=lambda: 657))

    page = client.execute_read("tidal_list_favorite_albums", listing_params(3, 12))
    assert page.items == []
    assert page.count == 0
    assert page.limit == 3
    assert page.offset == 12
    assert page.has_more is True
    assert page.next_offset == 15


def test_empty_uncounted_uncapped_page_keeps_the_scalar_envelope() -> None:
    client = TidalClient(favorites_listing_session(0))

    page = client.execute_read("tidal_list_favorite_albums", listing_params(3, 0))
    assert page.items == []
    assert page.count == 0
    assert page.value == []
    assert page.limit is None
    assert page.offset is None
    assert page.has_more is False
    assert page.next_offset is None


def test_empty_uncounted_capped_page_stays_paginated() -> None:
    client = TidalClient(favorites_listing_session(0))

    page = client.execute_read("tidal_list_favorite_mixes", listing_params(3, 9))
    assert page.items == []
    assert page.count == 0
    assert page.limit == 3
    assert page.offset == 9
    assert page.has_more is False
    assert page.next_offset is None


def test_undercounting_total_cannot_end_a_favorite_walk_early() -> None:
    client = TidalClient(favorites_listing_session(4, get_albums_count=lambda: 10))

    page = client.execute_read("tidal_list_favorite_albums", listing_params(3, 9))
    assert [item.id for item in page.items] == ["0", "1", "2"]
    assert page.count == 3
    assert page.has_more is True
    assert page.next_offset == 12


def recording_listing_session(page_items: int, **counters: Any) -> SimpleNamespace:
    recorded: list[int] = []

    def listing(**kwargs: Any) -> list[SimpleNamespace]:
        recorded.append(kwargs["limit"])
        return [SimpleNamespace(id=str(index)) for index in range(page_items)]

    favorites = SimpleNamespace(
        albums=listing,
        artists=listing,
        playlists=listing,
        videos=listing,
        mixes=listing,
        tracks=listing,
        playlist_folders=listing,
    )
    for name, value in counters.items():
        setattr(favorites, name, value)
    user = SimpleNamespace(
        favorites=favorites,
        public_playlists=listing,
        playlist_and_favorite_playlists=listing,
    )
    return SimpleNamespace(
        user=user,
        playlist=lambda _identifier: SimpleNamespace(items=listing),
        recorded=recorded,
    )


def test_capped_listings_never_ask_the_provider_for_more_than_fifty() -> None:
    session = recording_listing_session(2)
    client = TidalClient(session)

    client.execute_read("tidal_list_favorite_playlists", listing_params(50, 0))
    client.execute_read("tidal_list_favorite_mixes", listing_params(50, 0))
    client.execute_read(
        "tidal_list_playlist_folders",
        {**listing_params(50, 0), "parent_folder_id": "root"},
    )
    client.execute_read("tidal_list_public_playlists", {"limit": 50, "offset": 0})
    client.execute_read("tidal_list_playlists_and_favorites", {"limit": 50, "offset": 0})

    assert session.recorded == [50, 50, 50, 50, 50]


def test_uncapped_ordered_listings_keep_the_over_fetch_slot_at_fifty() -> None:
    session = recording_listing_session(2)
    client = TidalClient(session)

    client.execute_read("tidal_list_favorite_albums", listing_params(50, 0))
    client.execute_read("tidal_list_favorite_artists", listing_params(50, 0))
    client.execute_read("tidal_list_favorite_videos", listing_params(50, 0))
    client.execute_read(
        "tidal_get_playlist_items",
        {**listing_params(50, 0), "playlist_id": "playlist-1"},
    )

    assert session.recorded == [51, 51, 51, 51]


def test_uncapped_favorite_track_listing_still_over_fetches_at_the_maximum() -> None:
    session = recording_listing_session(2, get_tracks_count=lambda: 657)
    client = TidalClient(session)

    client.list_favorite_tracks(limit=50, offset=0)

    assert session.recorded == [51]


def test_capped_full_page_reports_more_work_without_an_over_fetch_slot() -> None:
    session = recording_listing_session(50)
    client = TidalClient(session)

    page = client.execute_read("tidal_list_favorite_mixes", listing_params(50, 100))
    assert session.recorded == [50]
    assert page.count == 50
    assert page.limit == 50
    assert page.offset == 100
    assert page.has_more is True
    assert page.next_offset == 150


def test_capped_short_page_without_a_counter_ends_the_walk() -> None:
    session = recording_listing_session(7)
    client = TidalClient(session)

    page = client.execute_read("tidal_list_favorite_mixes", listing_params(50, 0))
    assert session.recorded == [50]
    assert page.count == 7
    assert page.has_more is False
    assert page.next_offset is None


def test_capped_listing_below_the_provider_maximum_keeps_over_fetching() -> None:
    session = recording_listing_session(6)
    client = TidalClient(session)

    page = client.execute_read("tidal_list_favorite_mixes", listing_params(5, 0))
    assert session.recorded == [6]
    assert [item.id for item in page.items] == ["0", "1", "2", "3", "4"]
    assert page.count == 5
    assert page.has_more is True
    assert page.next_offset == 5


def offset_recording_listing_session(page_items: int) -> SimpleNamespace:
    recorded: list[dict[str, Any]] = []

    def listing(**kwargs: Any) -> list[SimpleNamespace]:
        recorded.append({"limit": kwargs["limit"], "offset": kwargs["offset"]})
        start = kwargs["offset"]
        return [SimpleNamespace(id=str(start + index)) for index in range(page_items)]

    favorites = SimpleNamespace(playlists=listing, mixes=listing)
    return SimpleNamespace(
        user=SimpleNamespace(favorites=favorites),
        recorded=recorded,
    )


def test_capped_listing_above_the_provider_maximum_clamps_the_reported_page() -> None:
    session = recording_listing_session(50)
    client = TidalClient(session)

    page = client.execute_read("tidal_list_favorite_mixes", listing_params(60, 100))
    assert session.recorded == [50]
    assert page.count == 50
    assert page.limit == 50
    assert page.offset == 100
    assert page.has_more is True
    assert page.next_offset == 150


def test_capped_walk_above_the_provider_maximum_skips_no_items() -> None:
    session = offset_recording_listing_session(50)
    client = TidalClient(session)

    first = client.execute_read("tidal_list_favorite_mixes", listing_params(60, 100))
    assert [item.id for item in first.items] == [str(value) for value in range(100, 150)]
    assert first.next_offset == 150

    second = client.execute_read("tidal_list_favorite_mixes", listing_params(60, first.next_offset))
    assert second.offset == first.next_offset
    assert [item.id for item in second.items] == [str(value) for value in range(150, 200)]
    assert [entry["limit"] for entry in session.recorded] == [50, 50]
    assert [item.id for item in first.items] + [item.id for item in second.items] == [
        str(value) for value in range(100, 200)
    ]


def test_uncapped_listing_above_the_provider_maximum_keeps_the_requested_limit() -> None:
    session = recording_listing_session(50)
    client = TidalClient(session)

    page = client.execute_read("tidal_list_favorite_albums", listing_params(60, 0))
    assert session.recorded == [61]
    assert page.count == 50
    assert page.limit == 60
    assert page.offset == 0
