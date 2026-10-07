from __future__ import annotations

import inspect
from types import SimpleNamespace
from typing import Any

import pytest
import tidalapi.types as tidal_types

from tidal_mcp.catalog import MUTATION_TOOL_SPECS, READ_TOOL_SPECS
from tidal_mcp.client import TidalClient
from tidal_mcp.exceptions import PartialPlaylistCreationError, TidalClientError
from tidal_mcp.models import CommitPlaylistResult, Playlist, Track, TrackPage


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


def test_show_more_strips_the_advertised_home_prefix() -> None:
    session = UniversalSession()
    requested: list[str] = []

    def page_get(api_path: str) -> EditorialPageNode:
        requested.append(api_path)
        return EditorialPageNode(api_path)

    session.page = SimpleNamespace(get=page_get)
    session.home = lambda: EditorialPageNode("home")
    category = CategoryNode()
    category._more = SimpleNamespace(api_path="home/pages/DAILY_MIXES/view-all")
    session.home = lambda: SimpleNamespace(
        title="Home",
        categories=[category],
    )
    client = TidalClient(session)

    result = client.execute_read(
        "tidal_show_more_page_category",
        {"page": "home", "category_index": 0},
    )
    assert requested == ["pages/DAILY_MIXES/view-all"]
    assert result.item.id == "pages/DAILY_MIXES/view-all"


def test_show_more_reports_an_empty_expansion_instead_of_failing() -> None:
    session = UniversalSession()

    def page_get(_api_path: str) -> Node:
        raise KeyError("items")

    session.page = SimpleNamespace(get=page_get)
    client = TidalClient(session)

    with pytest.raises(TidalClientError, match="no expandable items right now"):
        client.execute_read(
            "tidal_show_more_page_category",
            {"page": "home", "category_index": 0},
        )


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


class CollectablePlaylist:
    """A playlist whose pages are driven by a configurable item count."""

    def __init__(self, total: int, *, short_pages: bool = False) -> None:
        self.total = total
        self.short_pages = short_pages
        self.requests: list[tuple[int, int]] = []

    def tracks(self, limit: int, offset: int) -> list[SimpleNamespace]:
        self.requests.append((limit, offset))
        available = self.total - offset
        page = max(0, min(limit, available))
        if self.short_pages:
            # A provider can answer a window with fewer items than the window holds. The page is
            # short, but the collection is not over.
            page = min(page, 5)
        return [
            SimpleNamespace(
                id=str(offset + index),
                name=f"Track {offset + index}",
                artist=SimpleNamespace(id="artist-1", name="Artist"),
                album=SimpleNamespace(id="album-1", name="Album", release_date="2014-05-05"),
                duration=200,
                explicit=False,
                isrc=f"ISRC{offset + index}",
            )
            for index in range(page)
        ]


def playlist_session(playlist: CollectablePlaylist, *, title: str = "Fixture") -> SimpleNamespace:
    node = SimpleNamespace(
        id="playlist-1",
        name=title,
        description="Fixture playlist",
        creator=SimpleNamespace(username="owner"),
        num_tracks=playlist.total,
        duration=playlist.total * 200,
        created="2026-01-01",
        last_updated="2026-01-02",
        tracks=playlist.tracks,
        items=playlist.tracks,
        get_tracks_count=lambda: playlist.total,
    )
    return SimpleNamespace(playlist=lambda _identifier: node)


def test_collect_playlist_tracks_walks_every_page() -> None:
    playlist = CollectablePlaylist(120)
    client = TidalClient(playlist_session(playlist))

    collected = client.collect_playlist_tracks("playlist-1", max_items=500)

    assert collected.count == 120
    assert collected.truncated is False
    assert collected.pages_fetched == 3
    assert collected.max_items == 500
    assert [item.id for item in collected.items][:2] == ["0", "1"]
    assert playlist.requests == [(51, 0), (51, 50), (21, 100)]


def test_collect_playlist_tracks_reports_the_cap_as_truncated() -> None:
    playlist = CollectablePlaylist(200)
    client = TidalClient(playlist_session(playlist))

    collected = client.collect_playlist_tracks("playlist-1", max_items=75)

    assert collected.count == 75
    assert collected.truncated is True
    assert collected.max_items == 75
    assert len(collected.items) == 75


def test_collect_playlist_tracks_keeps_walking_after_a_short_page() -> None:
    playlist = CollectablePlaylist(120, short_pages=True)
    client = TidalClient(playlist_session(playlist))

    collected = client.collect_playlist_tracks("playlist-1", max_items=500)

    # Every page comes back with 5 items instead of the requested 50. A walk that trusted page
    # length alone would treat the first page as the end of the playlist; the exact counter keeps
    # it advancing until the total is covered.
    assert collected.pages_fetched == 3
    assert [offset for _, offset in playlist.requests] == [0, 50, 100]
    assert collected.count == 15
    assert collected.truncated is False


def test_collect_playlist_tracks_stops_on_a_stalled_cursor() -> None:
    class Stalled(CollectablePlaylist):
        def tracks(self, limit: int, offset: int) -> list[SimpleNamespace]:
            del limit, offset
            return [SimpleNamespace(id="only", name="Only", artist=None, album=None, duration=1)]

    client = TidalClient(playlist_session(Stalled(1), title="Stalled"))

    collected = client.collect_playlist_tracks("playlist-1", max_items=50)

    assert collected.count == 1
    assert collected.pages_fetched == 1


def test_summarize_playlist_derives_metrics_and_duplicates() -> None:
    playlist = CollectablePlaylist(6)
    session = playlist_session(playlist, title="Fixture Summary")

    def tracks(*, limit: int, offset: int) -> list[SimpleNamespace]:
        del limit
        if offset:
            return []
        return [
            SimpleNamespace(
                id=str(index),
                name="Same Song" if index % 2 == 0 else f"Song {index}",
                artist=SimpleNamespace(id="a-1", name="Repeat Artist"),
                album=SimpleNamespace(id="al-1", name="Album", release_date="2011-01-01"),
                duration=100,
                explicit=index % 2 == 1,
                isrc=None,
            )
            for index in range(6)
        ]

    session.playlist = lambda _identifier: SimpleNamespace(
        id="playlist-1",
        name="Fixture Summary",
        description="d",
        creator=SimpleNamespace(username="owner"),
        num_tracks=6,
        duration=600,
        created="2026-01-01",
        last_updated="2026-01-02",
        tracks=tracks,
        items=tracks,
        get_tracks_count=lambda: 6,
    )
    client = TidalClient(session)

    summary = client.summarize_playlist("playlist-1", max_items=100, top_artists=3)

    assert summary.playlist_id == "playlist-1"
    assert summary.title == "Fixture Summary"
    assert summary.tracks_analyzed == 6
    assert summary.truncated is False
    assert summary.total_duration_seconds == 600
    assert summary.distinct_artists == 1
    assert summary.top_artists[0].artist == "Repeat Artist"
    assert summary.top_artists[0].track_count == 6
    assert summary.decade_counts == {"2010s": 6}
    assert summary.explicit_tracks == 3
    assert summary.tracks_without_release_date == 0
    assert summary.duplicate_tracks[0].title == "Same Song"
    assert summary.duplicate_tracks[0].occurrences == 3


def test_summarize_playlist_counts_unparseable_release_dates() -> None:
    def tracks(*, limit: int, offset: int) -> list[SimpleNamespace]:
        del limit
        if offset:
            return []
        return [
            SimpleNamespace(
                id="1",
                name="No Date",
                artist=SimpleNamespace(id="a", name="Artist"),
                album=None,
                duration=10,
                explicit=True,
                isrc=None,
                release_date=None,
            )
        ]

    session = SimpleNamespace(
        playlist=lambda _identifier: SimpleNamespace(
            id="p",
            name="Untitled",
            description="",
            creator=None,
            num_tracks=1,
            duration=10,
            created=None,
            last_updated=None,
            tracks=tracks,
            items=tracks,
            get_tracks_count=lambda: 1,
        )
    )
    client = TidalClient(session)

    summary = client.summarize_playlist("p", max_items=10, top_artists=1)

    assert summary.tracks_analyzed == 1
    assert summary.decade_counts == {}
    assert summary.tracks_without_release_date == 1
    assert summary.duplicate_tracks == []
    assert summary.total_duration_seconds == 10


def test_collect_playlist_tracks_without_a_counter_uses_the_page_signal() -> None:
    class NoCounter(CollectablePlaylist):
        def tracks(self, *, limit: int, offset: int) -> list[SimpleNamespace]:
            self.requests.append((limit, offset))
            available = self.total - offset
            page = max(0, min(limit, available))
            return [
                SimpleNamespace(
                    id=str(offset + index),
                    name=f"Track {offset + index}",
                    artist=None,
                    album=None,
                    duration=1,
                    isrc=None,
                )
                for index in range(page)
            ]

    playlist = NoCounter(4)
    session = playlist_session(playlist)
    node = session.playlist("x")
    del node.get_tracks_count  # TIDAL did not provide a counter
    client = TidalClient(session)

    collected = client.collect_playlist_tracks("playlist-1", max_items=100)

    assert collected.count == 4
    assert collected.truncated is False


def test_collect_playlist_tracks_reports_a_failed_count() -> None:
    playlist = CollectablePlaylist(3)
    session = playlist_session(playlist)

    def exploding_count() -> int:
        raise RuntimeError("counter unavailable")

    session.playlist("x").get_tracks_count = exploding_count
    client = TidalClient(session)

    collected = client.collect_playlist_tracks("playlist-1", max_items=100)

    assert collected.count == 3


def test_summarize_playlist_survives_a_missing_title() -> None:
    playlist = CollectablePlaylist(2)
    session = playlist_session(playlist)
    node = session.playlist("x")

    class NoName:
        pass

    session.playlist = lambda _identifier: SimpleNamespace(
        tracks=node.tracks,
        items=node.items,
        get_tracks_count=node.get_tracks_count,
    )
    client = TidalClient(session)

    summary = client.summarize_playlist("playlist-1", max_items=10, top_artists=1)

    assert summary.title is None
    assert summary.tracks_analyzed == 2
    assert summary.distinct_artists == 1


def test_collect_playlist_tracks_wraps_an_unexpected_upstream_failure() -> None:
    class Exploding(CollectablePlaylist):
        def tracks(self, *, limit: int, offset: int) -> list[SimpleNamespace]:
            del limit, offset
            raise RuntimeError("upstream detail that must not leak")

    client = TidalClient(playlist_session(Exploding(1)))

    with pytest.raises(TidalClientError) as caught:
        client.collect_playlist_tracks("playlist-1", max_items=10)

    assert "upstream detail" not in str(caught.value)


def test_collect_playlist_tracks_handles_a_zero_width_window() -> None:
    """A counter that shrinks below the cursor ends the walk instead of requesting an empty page."""

    class Shrinking(CollectablePlaylist):
        def tracks(self, *, limit: int, offset: int) -> list[SimpleNamespace]:
            self.requests.append((limit, offset))
            return []

    playlist = Shrinking(10)
    session = playlist_session(playlist)
    # An empty playlist reports a total of zero, so the walk must not request a zero-width window.
    session.playlist("x").get_tracks_count = lambda: 0
    client = TidalClient(session)

    collected = client.collect_playlist_tracks("playlist-1", max_items=100)

    assert collected.count == 0
    assert collected.pages_fetched == 0
    assert collected.truncated is False


def test_collect_playlist_tracks_stops_when_the_cursor_does_not_advance() -> None:
    class Frozen(CollectablePlaylist):
        def tracks(self, *, limit: int, offset: int) -> list[SimpleNamespace]:
            del limit, offset
            return [
                SimpleNamespace(
                    id="fixed",
                    name="Fixed",
                    artist=None,
                    album=None,
                    duration=1,
                    isrc=None,
                )
            ]

    playlist = Frozen(1)
    session = playlist_session(playlist)
    del session.playlist("x").get_tracks_count
    client = TidalClient(session)

    collected = client.collect_playlist_tracks("playlist-1", max_items=50)

    assert collected.count == 1
    assert collected.pages_fetched == 1


def test_collect_playlist_tracks_without_a_counter_ends_on_the_last_page() -> None:
    class Paged(CollectablePlaylist):
        def tracks(self, *, limit: int, offset: int) -> list[SimpleNamespace]:
            self.requests.append((limit, offset))
            available = self.total - offset
            page = max(0, min(limit, available))
            return [
                SimpleNamespace(
                    id=str(offset + index),
                    name=f"Track {offset + index}",
                    artist=None,
                    album=None,
                    duration=1,
                    isrc=None,
                )
                for index in range(page)
            ]

    playlist = Paged(3)
    session = playlist_session(playlist)
    del session.playlist("x").get_tracks_count
    client = TidalClient(session)

    collected = client.collect_playlist_tracks("playlist-1", max_items=2)

    assert collected.count == 2
    assert collected.truncated is True


def test_collect_playlist_tracks_walks_two_windows_without_a_counter(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Without an exact counter the page signal must still allow a next window."""
    session = playlist_session(CollectablePlaylist(5))
    node = session.playlist("x")
    del node.get_tracks_count  # force the path that trusts the cursor
    client = TidalClient(session)
    track = Track(id="1", title="One", artist="A", url="https://tidal.com/browse/track/1")
    pages = [
        TrackPage(items=[track], count=1, limit=1, offset=0, has_more=True, next_offset=1),
        TrackPage(items=[track], count=1, limit=1, offset=1, has_more=False, next_offset=None),
    ]
    monkeypatch.setattr(client, "_playlist_page", lambda *_a, **_k: pages.pop(0))

    collected = client.collect_playlist_tracks("playlist-1", max_items=50)

    assert collected.count == 2
    assert collected.pages_fetched == 2
    assert collected.truncated is False


def test_collect_playlist_tracks_stops_on_a_frozen_provider_cursor(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A cursor that never advances would loop forever without the defensive check."""
    session = playlist_session(CollectablePlaylist(5))
    node = session.playlist("x")
    del node.get_tracks_count  # force the path that trusts the cursor
    client = TidalClient(session)
    track = Track(id="1", title="One", artist="A", url="https://tidal.com/browse/track/1")
    frozen = TrackPage(
        items=[track],
        count=1,
        limit=1,
        offset=0,
        has_more=True,
        next_offset=0,
    )
    monkeypatch.setattr(client, "_playlist_page", lambda *_a, **_k: frozen)

    collected = client.collect_playlist_tracks("playlist-1", max_items=50)

    assert collected.count == 1
    assert collected.pages_fetched == 1


def test_collect_playlist_tracks_wraps_a_non_tidal_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session = playlist_session(CollectablePlaylist(5))
    node = session.playlist("x")
    del node.get_tracks_count
    client = TidalClient(session)

    def explode(*_args: object, **_kwargs: object) -> None:
        raise ValueError("raw upstream detail")

    monkeypatch.setattr(client, "_playlist_page", explode)

    with pytest.raises(TidalClientError) as caught:
        client.collect_playlist_tracks("playlist-1", max_items=10)

    assert "raw upstream detail" not in str(caught.value)


def test_collect_playlist_tracks_with_an_empty_playlist_skips_the_loop() -> None:
    """An empty playlist has nothing to walk, so the loop body must never run."""
    playlist = CollectablePlaylist(0)
    client = TidalClient(playlist_session(playlist))

    collected = client.collect_playlist_tracks("playlist-1", max_items=50)

    assert collected.count == 0
    assert collected.pages_fetched == 0
    assert playlist.requests == []


def test_collect_playlist_tracks_is_not_truncated_when_the_cap_lands_exactly_on_the_end() -> None:
    """A cap that equals the playlist length is a complete result, not a truncated one."""
    playlist = CollectablePlaylist(50)
    client = TidalClient(playlist_session(playlist))

    collected = client.collect_playlist_tracks("playlist-1", max_items=50)

    assert collected.count == 50
    assert collected.truncated is False


def test_collect_playlist_tracks_is_truncated_when_a_capped_page_still_has_more() -> None:
    """Without a counter, a full capped page that reports more work is a truncation."""
    client = TidalClient(playlist_session(CollectablePlaylist(120)))
    client.get_playlist_tracks = lambda *_a, **_k: TrackPage(  # type: ignore[method-assign]
        items=[
            Track(id=str(i), title=f"T{i}", artist="A", url=f"https://tidal.com/browse/track/{i}")
            for i in range(2)
        ],
        count=2,
        limit=2,
        offset=0,
        has_more=True,
        next_offset=2,
    )
    client._playlist_track_count = lambda _identifier: None  # type: ignore[method-assign]

    collected = client.collect_playlist_tracks("playlist-1", max_items=2)

    assert collected.count == 2
    assert collected.truncated is True


def test_collect_wraps_a_resolution_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    client = TidalClient(playlist_session(CollectablePlaylist(3)))

    def explode(_identifier: str):
        raise ValueError("raw resolution detail")

    monkeypatch.setattr(client, "_resolve_playlist", explode)

    with pytest.raises(TidalClientError) as caught:
        client.collect_playlist_tracks("playlist-1", max_items=10)

    assert "raw resolution detail" not in str(caught.value)


def test_collect_wraps_a_count_failure_inside_the_walk(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A failure while walking still surfaces as a safe tool error, not a raw exception."""
    client = TidalClient(playlist_session(CollectablePlaylist(3)))

    def explode(*_args: object, **_kwargs: object) -> None:
        raise ValueError("raw walk detail")

    monkeypatch.setattr(client, "_playlist_page", explode)

    with pytest.raises(TidalClientError) as caught:
        client.collect_playlist_tracks("playlist-1", max_items=10)

    assert "raw walk detail" not in str(caught.value)


def test_collect_for_export_wraps_a_resolution_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = TidalClient(playlist_session(CollectablePlaylist(3)))

    def explode(_identifier: str):
        raise ValueError("raw export detail")

    monkeypatch.setattr(client, "_resolve_playlist", explode)

    with pytest.raises(TidalClientError) as caught:
        client.collect_playlist_for_export("playlist-1", max_items=10)

    assert "raw export detail" not in str(caught.value)


def test_summarize_wraps_a_resolution_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    client = TidalClient(playlist_session(CollectablePlaylist(3)))

    def explode(_identifier: str):
        raise ValueError("raw summary detail")

    monkeypatch.setattr(client, "_resolve_playlist", explode)

    with pytest.raises(TidalClientError) as caught:
        client.summarize_playlist("playlist-1", max_items=10, top_artists=1)

    assert "raw summary detail" not in str(caught.value)


def _raising_client(monkeypatch: pytest.MonkeyPatch, message: str) -> TidalClient:
    """A client whose playlist resolution raises an expected domain error."""
    client = TidalClient(playlist_session(CollectablePlaylist(3)))

    def explode(_identifier: str) -> None:
        raise TidalClientError(message)

    monkeypatch.setattr(client, "_resolve_playlist", explode)
    return client


def test_expected_domain_errors_pass_through_unwrapped(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A TidalClientError is already a safe message, so it must not be re-wrapped."""
    client = _raising_client(monkeypatch, "playlist is unavailable")

    with pytest.raises(TidalClientError, match="playlist is unavailable"):
        client.collect_playlist_tracks("playlist-1", max_items=10)


def test_the_inner_walk_reraises_a_domain_error_from_a_page(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = TidalClient(playlist_session(CollectablePlaylist(3)))

    def explode(*_args: object, **_kwargs: object) -> None:
        raise TidalClientError("page failed safely")

    monkeypatch.setattr(client, "_playlist_page", explode)

    with pytest.raises(TidalClientError, match="page failed safely"):
        client.collect_playlist_tracks("playlist-1", max_items=10)


def test_export_helper_reraises_a_domain_error(monkeypatch: pytest.MonkeyPatch) -> None:
    client = _raising_client(monkeypatch, "export precondition failed")

    with pytest.raises(TidalClientError, match="export precondition failed"):
        client.collect_playlist_for_export("playlist-1", max_items=10)


def test_summarize_reraises_a_domain_error(monkeypatch: pytest.MonkeyPatch) -> None:
    client = _raising_client(monkeypatch, "summary precondition failed")

    with pytest.raises(TidalClientError, match="summary precondition failed"):
        client.summarize_playlist("playlist-1", max_items=10, top_artists=1)


def test_export_helper_returns_the_title_and_collected_tracks() -> None:
    client = TidalClient(playlist_session(CollectablePlaylist(4), title="Export Me"))

    title, collected = client.collect_playlist_for_export("playlist-1", max_items=10)

    assert title == "Export Me"
    assert collected.count == 4


def test_compare_reraises_a_domain_error_from_a_side(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = TidalClient(playlist_session(CollectablePlaylist(3)))

    def explode(*_args: object, **_kwargs: object) -> None:
        raise TidalClientError("side failed safely")

    monkeypatch.setattr(client, "_collect_playlist", explode)

    with pytest.raises(TidalClientError, match="side failed safely"):
        client.compare_playlists("left", "right", max_items=10)
