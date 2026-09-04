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
