from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from enum import Enum
from types import SimpleNamespace

from tidal_mcp.formatting import _safe_json, _text, _value, format_catalog_result, public_item


class Constructible:
    def __init__(self, **values: object) -> None:
        self.__dict__.update(values)


def object_named(class_name: str, **values: object) -> object:
    return type(class_name, (Constructible,), {})(**values)


def media_values(identifier: str = "1") -> dict[str, object]:
    artist = SimpleNamespace(id="artist-1", name="Artist")
    album = SimpleNamespace(id="album-1", name="Album", release_date="2024-01-01")
    return {
        "id": identifier,
        "name": "Title",
        "title": "Title",
        "artist": artist,
        "album": album,
        "duration": 180,
        "explicit": False,
        "release_date": "2024-01-02",
        "num_tracks": 1,
        "creator": SimpleNamespace(username="owner"),
        "description": "Description",
        "created": "2024-01-01",
        "last_updated": "2024-01-02",
    }


def test_public_item_formats_every_first_class_media_type() -> None:
    assert public_item(object_named("Track", **media_values())).type == "track"
    assert public_item(object_named("Album", **media_values())).type == "album"
    assert public_item(object_named("Playlist", **media_values())).type == "playlist"
    assert public_item(object_named("UserPlaylist", **media_values())).type == "playlist"
    assert public_item(object_named("Artist", id="artist-1", name="Artist")).type == "artist"


def test_public_item_allowlist_handles_extended_objects_and_nested_values() -> None:
    image = object_named("ImageResponse", small="s", medium="m", large="l")
    mix_type = Enum("FixtureEnum", {"VALUE": "DAILY_MIX"}).VALUE
    video = object_named(
        "Video",
        id="video-1",
        title="Video",
        duration=60,
        explicit=False,
        quality="HIGH",
        release_date=datetime(2024, 1, 1, tzinfo=UTC),
        image_id="image",
    )
    mix = object_named(
        "Mix",
        id="mix-1",
        title="Mix",
        sub_title="Daily",
        short_subtitle="Today",
        mix_type=mix_type,
        images=image,
    )
    page = object_named("Page", title="Home", categories=[mix, video])
    assert public_item(video).url.endswith("/video/video-1")
    formatted_mix = public_item(mix)
    assert formatted_mix.url.endswith("/mix/mix-1")
    assert formatted_mix.details["mix_type"] == "DAILY_MIX"
    assert public_item(page).details["categories"][0]["type"] == "mix"
    assert public_item(SimpleNamespace(id="x")).type == "simplenamespace"


def test_public_item_formats_page_links_and_page_items() -> None:
    link = object_named(
        "PageLink",
        title="Browse Rock",
        icon="genre",
        api_path="pages/rock",
        image_id="image-1",
    )
    formatted_link = public_item(link)
    assert formatted_link.type == "page_link"
    assert formatted_link.id == "pages/rock"
    assert formatted_link.title == "Browse Rock"
    assert formatted_link.details == {"icon": "genre", "image_id": "image-1"}

    item = object_named(
        "PageItem",
        header="Featured",
        short_header="Featured",
        short_sub_header="Today",
        type="ALBUM",
        artifact_id="album-1",
        text="Editorial text",
        featured=True,
    )
    formatted_item = public_item(item)
    assert formatted_item.type == "page_item"
    assert formatted_item.id == "album-1"
    assert formatted_item.title == "Featured"
    assert formatted_item.details["type"] == "ALBUM"
    assert formatted_item.details["featured"] is True


def test_page_categories_advertise_an_available_show_more_flow() -> None:
    with_more = object_named(
        "ItemList",
        type="ALBUM_LIST",
        title="Albums",
        description="",
        items=[],
        _more=SimpleNamespace(api_path="pages/more"),
    )
    without_more = object_named(
        "ItemList",
        type="ALBUM_LIST",
        title="Albums",
        description="",
        items=[],
        _more=None,
    )
    assert public_item(with_more).details["show_more_available"] is True
    assert "show_more_available" not in public_item(without_more).details


def test_safe_json_covers_scalars_dates_collections_dataclasses_and_depth() -> None:
    @dataclass
    class Fixture:
        value: int

    assert _safe_json(None) is None
    assert _safe_json(3) == 3
    assert _safe_json(datetime(2024, 1, 1, tzinfo=UTC)).startswith("2024-01-01")
    assert _safe_json((1, 2)) == [1, 2]
    assert _safe_json({"ok": 1, "_private": 2}) == {"ok": 1}
    assert _safe_json(Fixture(4)) == {"value": 4}
    assert _safe_json(SimpleNamespace(id="x"))["id"] == "x"
    assert _safe_json("hidden", depth=5) is None


def test_catalog_result_variants_and_pagination() -> None:
    nodes = [SimpleNamespace(id="1"), SimpleNamespace(id="2")]
    page = format_catalog_result("list", nodes, limit=1, offset=4, warnings=["fixture"])
    assert page.count == 1
    assert page.has_more is True
    assert page.next_offset == 5
    assert page.warnings == ["fixture"]
    unbounded = format_catalog_result("list", nodes)
    assert unbounded.count == 2
    assert unbounded.has_more is False
    assert format_catalog_result("text", "hello").text == "hello"
    assert format_catalog_result("none", None).value is None
    assert format_catalog_result("scalar", [1, 2]).value == [1, 2]
    assert format_catalog_result("item", SimpleNamespace(id="1")).item.id == "1"


def test_defensive_value_and_text_helpers() -> None:
    class Explodes:
        @property
        def broken(self) -> str:
            raise RuntimeError("boom")

    assert _value(Explodes(), "broken", "safe") == "safe"
    assert _value(SimpleNamespace(value=None), "value", "safe") == "safe"
    assert _text(None) is None
    assert _text(datetime(2024, 1, 1, tzinfo=UTC)).startswith("2024-01-01")


def test_counted_pages_stay_paginated_when_empty_or_undercounted() -> None:
    empty = format_catalog_result("list", [], limit=3, offset=12, total=657)
    assert empty.items == []
    assert empty.count == 0
    assert empty.limit == 3
    assert empty.offset == 12
    assert empty.has_more is True
    assert empty.next_offset == 15

    exhausted = format_catalog_result("list", [], limit=3, offset=654, total=657)
    assert exhausted.count == 0
    assert exhausted.has_more is False
    assert exhausted.next_offset is None

    nodes = [SimpleNamespace(id=str(index)) for index in range(4)]
    undercounted = format_catalog_result("list", nodes, limit=3, offset=9, total=10)
    assert [item.id for item in undercounted.items] == ["0", "1", "2"]
    assert undercounted.has_more is True
    assert undercounted.next_offset == 12


def nodes(count: int) -> list[SimpleNamespace]:
    return [SimpleNamespace(id=str(index)) for index in range(count)]


def test_fetched_window_decides_the_over_fetch_signal() -> None:
    exact = format_catalog_result("list", nodes(3), limit=3, offset=0, fetched=4)
    assert exact.count == 3
    assert exact.has_more is False
    assert exact.next_offset is None

    over = format_catalog_result("list", nodes(4), limit=3, offset=0, fetched=4)
    assert over.count == 3
    assert over.has_more is True
    assert over.next_offset == 3

    capped_full = format_catalog_result("list", nodes(3), limit=3, offset=6, fetched=3)
    assert capped_full.count == 3
    assert capped_full.has_more is True
    assert capped_full.next_offset == 9

    capped_short = format_catalog_result("list", nodes(2), limit=3, offset=6, fetched=3)
    assert capped_short.count == 2
    assert capped_short.has_more is False
    assert capped_short.next_offset is None


def test_empty_clamped_page_stays_paginated_without_a_counter() -> None:
    empty = format_catalog_result("list", [], limit=50, offset=100, fetched=50)
    assert empty.items == []
    assert empty.count == 0
    assert empty.limit == 50
    assert empty.offset == 100
    assert empty.has_more is False
    assert empty.next_offset is None


def test_absent_fetched_window_keeps_the_length_sentinel() -> None:
    full = format_catalog_result("list", nodes(3), limit=3, offset=0)
    assert full.has_more is False
    assert full.next_offset is None

    spilling = format_catalog_result("list", nodes(4), limit=3, offset=0)
    assert spilling.count == 3
    assert spilling.has_more is True
    assert spilling.next_offset == 3
