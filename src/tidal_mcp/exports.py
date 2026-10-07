"""Write playlist exports to a local file inside one controlled directory.

Exporting is the only feature that writes outside the approval-token flow. That makes the file
path the security boundary: a caller-supplied name must never escape the export directory, and the
server must never overwrite an existing file silently.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from tidal_mcp.config import ensure_private_directory, secure_file
from tidal_mcp.exceptions import ExportError
from tidal_mcp.models import DerivedExportResult, ExportResult, Track

UNSAFE_NAME = re.compile(r"[^A-Za-z0-9._-]+")


def safe_filename(name: str, *, suffix: str) -> str:
    """Reduce a caller-supplied name to a single safe path segment with the right extension.

    Every path separator, traversal sequence, and shell metacharacter is replaced, so the result
    can only ever be a file name inside the export directory. An empty result falls back to a
    fixed name rather than producing a hidden file or an error.
    """
    candidate = UNSAFE_NAME.sub("-", name).strip(".-")
    candidate = candidate[:80] or "tidal-playlist"
    if not candidate.lower().endswith(suffix):
        candidate = f"{candidate}{suffix}"
    return candidate


def render_json(tracks: list[Track]) -> str:
    """Render an export as a stable JSON document."""
    payload = {
        "track_count": len(tracks),
        "tracks": [track.model_dump(exclude_none=True) for track in tracks],
    }
    return json.dumps(payload, indent=2, ensure_ascii=False) + "\n"


def render_m3u(tracks: list[Track]) -> str:
    """Render an extended M3U playlist that points at TIDAL, not at local audio files.

    The entries use each track's public TIDAL URL, because this project never downloads media.
    The duration is the extended-M3U field, and it is emitted only when known.
    """
    lines = ["#EXTM3U"]
    for track in tracks:
        duration = track.duration_seconds if track.duration_seconds is not None else -1
        lines.append(f"#EXTINF:{duration},{track.artist} - {track.title}")
        lines.append(track.url)
    return "\n".join(lines) + "\n"


def write_export(
    *,
    export_dir: Path,
    playlist_id: str,
    title: str | None,
    tracks: list[Track],
    export_format: str,
    name: str | None,
    truncated: bool,
) -> ExportResult:
    """Write one export atomically and return what was written.

    The file is created in a private directory with a temporary name and then moved into place, so
    a reader never sees a partially written export. An existing target is refused instead of being
    overwritten, because silently replacing a file the user made is not recoverable.
    """
    suffix = ".json" if export_format == "json" else ".m3u"
    content = render_json(tracks) if export_format == "json" else render_m3u(tracks)
    target, written = _write_atomically(
        export_dir=export_dir,
        suggested_name=name or title or "tidal-playlist",
        suffix=suffix,
        content=content,
    )

    return ExportResult(
        playlist_id=playlist_id,
        title=title,
        format=export_format,
        path=str(target),
        track_count=len(tracks),
        bytes_written=written,
        truncated=truncated,
    )


def _write_atomically(
    *,
    export_dir: Path,
    suggested_name: str,
    suffix: str,
    content: str,
) -> tuple[Path, int]:
    """Write content into the export directory without ever clobbering an existing file.

    This is the single place that touches the filesystem, so the three guarantees live here: the
    directory is created privately, the name is reduced to one path segment, and the write goes
    through a temporary file that is moved into place only once it is complete.
    """
    directory = ensure_private_directory(export_dir)
    filename = safe_filename(suggested_name, suffix=suffix)
    target = directory / filename
    if target.exists():
        raise ExportError(
            f"{filename} already exists in the export directory. Choose another name."
        )
    temporary = directory / f".{filename}.partial"
    try:
        temporary.write_text(content, encoding="utf-8")
        secure_file(temporary)
        temporary.replace(target)
        secure_file(target)
    finally:
        if temporary.exists():
            temporary.unlink()
    return target, len(content.encode("utf-8"))


def render_derived_json(payload: dict[str, Any]) -> str:
    """Render a derived result, such as a summary or a comparison, as a JSON document."""
    return json.dumps(payload, indent=2, ensure_ascii=False) + "\n"


def write_derived_export(
    *,
    export_dir: Path,
    kind: str,
    suggested_name: str,
    payload: dict[str, Any],
) -> DerivedExportResult:
    """Write a summary or comparison to a JSON file inside the export directory.

    Derived results are JSON-only on purpose: they are structured analysis, not a track list, so an
    M3U would have no meaning. They share the track export's safety guarantees because they go
    through the same writer.
    """
    content = render_derived_json(payload)
    target, written = _write_atomically(
        export_dir=export_dir,
        suggested_name=suggested_name,
        suffix=".json",
        content=content,
    )
    return DerivedExportResult(
        kind=kind,
        format="json",
        path=str(target),
        bytes_written=written,
    )
