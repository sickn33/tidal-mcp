"""Convert tidalapi objects into stable public models."""

from __future__ import annotations

from dataclasses import asdict, is_dataclass
from datetime import date, datetime
from enum import Enum
from typing import Any

from tidal_mcp.models import Album, Artist, CatalogResult, Playlist, PublicItem, Track


def _value(obj: Any, name: str, default: Any = None) -> Any:
    try:
        value = getattr(obj, name, default)
    except Exception:
        return default
    return default if value is None else value


def _identifier(obj: Any) -> str | None:
    value = _value(obj, "id")
    return str(value) if value is not None else None


def _text(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    return str(value)


def format_track(item: Any, *, source_seed_ids: list[str] | None = None) -> Track:
    artist = _value(item, "artist")
    album = _value(item, "album")
    track_id = _identifier(item)
    if track_id is None:
        raise ValueError("TIDAL returned a track without an id")

    release_date = (
        _value(item, "release_date")
        or _value(item, "stream_start_date")
        or _value(album, "release_date")
    )
    return Track(
        id=track_id,
        title=str(_value(item, "name", _value(item, "title", "Unknown Track"))),
        artist=str(_value(artist, "name", "Unknown Artist")),
        artist_id=_identifier(artist),
        album=_text(_value(album, "name", _value(album, "title"))),
        album_id=_identifier(album),
        duration_seconds=_value(item, "duration"),
        explicit=_value(item, "explicit"),
        release_date=_text(release_date),
        url=f"https://tidal.com/browse/track/{track_id}",
        source_seed_ids=source_seed_ids or [],
    )


def format_album(item: Any) -> Album:
    artist = _value(item, "artist")
    album_id = _identifier(item)
    if album_id is None:
        raise ValueError("TIDAL returned an album without an id")
    return Album(
        id=album_id,
        title=str(_value(item, "name", _value(item, "title", "Unknown Album"))),
        artist=_text(_value(artist, "name")),
        artist_id=_identifier(artist),
        release_date=_text(_value(item, "release_date")),
        track_count=_value(item, "num_tracks"),
        duration_seconds=_value(item, "duration"),
        explicit=_value(item, "explicit"),
        url=f"https://tidal.com/browse/album/{album_id}",
    )


def format_artist(item: Any) -> Artist:
    artist_id = _identifier(item)
    if artist_id is None:
        raise ValueError("TIDAL returned an artist without an id")
    return Artist(
        id=artist_id,
        name=str(_value(item, "name", "Unknown Artist")),
        url=f"https://tidal.com/browse/artist/{artist_id}",
    )


def format_playlist(item: Any) -> Playlist:
    creator = _value(item, "creator")
    playlist_id = _identifier(item)
    if playlist_id is None:
        raise ValueError("TIDAL returned a playlist without an id")
    return Playlist(
        id=playlist_id,
        title=str(_value(item, "name", _value(item, "title", "Untitled Playlist"))),
        description=_text(_value(item, "description")),
        creator=_text(_value(creator, "name", _value(creator, "username"))),
        track_count=_value(item, "num_tracks"),
        duration_seconds=_value(item, "duration"),
        created_at=_text(_value(item, "created")),
        updated_at=_text(_value(item, "last_updated")),
        url=f"https://tidal.com/browse/playlist/{playlist_id}",
    )


_PUBLIC_FIELDS: dict[str, tuple[str, ...]] = {
    "Video": (
        "id",
        "name",
        "title",
        "duration",
        "explicit",
        "quality",
        "release_date",
        "image_id",
    ),
    "Mix": ("id", "title", "sub_title", "short_subtitle", "mix_type", "images"),
    "MixV2": (
        "id",
        "title",
        "sub_title",
        "short_subtitle",
        "mix_type",
        "date_added",
        "updated",
        "images",
        "detail_images",
    ),
    "Folder": ("id", "name", "parent_id", "created_at", "last_modified_at", "trn"),
    "Genre": ("name", "path", "playlists", "artists", "albums", "tracks", "videos", "image"),
    "Lyrics": (
        "track_id",
        "lyrics_provider",
        "provider_commontrack_id",
        "provider_lyrics_id",
        "subtitles",
        "lyrics",
        "is_right_to_left",
    ),
    "Stream": (
        "track_id",
        "audio_mode",
        "audio_quality",
        "manifest_mime_type",
        "bit_depth",
        "sample_rate",
    ),
    "Page": ("title", "categories"),
    "ItemList": ("type", "title", "description", "items"),
    "TrackList": ("type", "title", "subtitle", "description", "items"),
    "ShortcutList": ("type", "title", "subtitle", "description", "items"),
    "HorizontalList": ("type", "title", "subtitle", "description", "items"),
    "HorizontalListWithContext": (
        "type",
        "title",
        "subtitle",
        "description",
        "items",
    ),
    "PageLinks": ("type", "title", "description", "items"),
    "LinkList": ("type", "title", "description", "items"),
    "TextBlock": ("type", "title", "description", "text"),
    "FeaturedItems": ("type", "title", "description", "items"),
}


def _safe_json(value: Any, *, depth: int = 0) -> Any:
    """Convert explicitly selected public values without traversing session internals."""
    if depth > 4:
        return None
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if isinstance(value, Enum):
        return _safe_json(value.value, depth=depth + 1)
    if isinstance(value, (list, tuple)):
        return [_safe_json(item, depth=depth + 1) for item in value]
    if isinstance(value, dict):
        return {
            str(key): _safe_json(item, depth=depth + 1)
            for key, item in value.items()
            if not str(key).startswith("_")
        }
    if is_dataclass(value):
        return _safe_json(asdict(value), depth=depth + 1)
    return public_item(value, depth=depth + 1).model_dump(exclude_none=True)


def public_item(item: Any, *, depth: int = 0) -> PublicItem:
    """Format supported tidalapi objects using a strict public-field allowlist."""
    class_name = type(item).__name__
    if class_name == "Track":
        data = format_track(item).model_dump(exclude_none=True)
        return PublicItem(
            type="track",
            id=data.pop("id"),
            title=data.pop("title"),
            url=data.pop("url"),
            details=data,
        )
    if class_name == "Album":
        data = format_album(item).model_dump(exclude_none=True)
        return PublicItem(
            type="album",
            id=data.pop("id"),
            title=data.pop("title"),
            url=data.pop("url"),
            details=data,
        )
    if class_name in {"Playlist", "UserPlaylist"}:
        data = format_playlist(item).model_dump(exclude_none=True)
        return PublicItem(
            type="playlist",
            id=data.pop("id"),
            title=data.pop("title"),
            url=data.pop("url"),
            details=data,
        )
    if class_name == "Artist":
        data = format_artist(item).model_dump(exclude_none=True)
        return PublicItem(
            type="artist",
            id=data.pop("id"),
            name=data.pop("name"),
            url=data.pop("url"),
            details=data,
        )

    fields = _PUBLIC_FIELDS.get(class_name, ())
    details = {
        field: _safe_json(_value(item, field), depth=depth + 1)
        for field in fields
        if _value(item, field) is not None
    }
    identifier = _identifier(item)
    title = _text(details.pop("title", None))
    name = _text(details.pop("name", None))
    url = None
    if identifier and class_name in {"Video", "Mix", "MixV2"}:
        route = "mix" if class_name.startswith("Mix") else "video"
        url = f"https://tidal.com/browse/{route}/{identifier}"
    return PublicItem(
        type=class_name.lower() or "unknown",
        id=identifier,
        title=title,
        name=name,
        url=url,
        details=details,
    )


def format_catalog_result(
    operation: str,
    value: Any,
    *,
    limit: int | None = None,
    offset: int | None = None,
    warnings: list[str] | None = None,
) -> CatalogResult:
    """Build one predictable envelope for objects, lists, prose, and scalar metadata."""
    if isinstance(value, list) and not all(
        isinstance(item, (str, int, float, bool, list, tuple, dict)) for item in value
    ):
        has_more = limit is not None and len(value) > limit
        selected = value[:limit] if limit is not None else value
        return CatalogResult(
            operation=operation,
            items=[public_item(item) for item in selected if item is not None],
            count=len(selected),
            limit=limit,
            offset=offset,
            has_more=has_more,
            next_offset=(offset or 0) + limit if has_more and limit is not None else None,
            warnings=warnings or [],
        )
    if isinstance(value, str):
        return CatalogResult(operation=operation, text=value, warnings=warnings or [])
    if value is None or isinstance(value, (bool, int, float, list, tuple, dict)):
        return CatalogResult(
            operation=operation,
            value=_safe_json(value),
            warnings=warnings or [],
        )
    return CatalogResult(
        operation=operation,
        item=public_item(value),
        count=1,
        warnings=warnings or [],
    )
