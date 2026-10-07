"""Write playlist exports to a local file inside one controlled directory.

Exporting is the only feature that writes outside the approval-token flow. That makes the file
path the security boundary: a caller-supplied name must never escape the export directory, and the
server must never overwrite an existing file silently.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from tidal_mcp.config import ensure_private_directory, secure_file
from tidal_mcp.exceptions import ExportError
from tidal_mcp.models import ExportResult, Track

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
    directory = ensure_private_directory(export_dir)
    filename = safe_filename(name or title or "tidal-playlist", suffix=suffix)
    target = directory / filename
    if target.exists():
        raise ExportError(
            f"{filename} already exists in the export directory. Choose another name."
        )

    content = render_json(tracks) if export_format == "json" else render_m3u(tracks)
    temporary = directory / f".{filename}.partial"
    try:
        temporary.write_text(content, encoding="utf-8")
        secure_file(temporary)
        temporary.replace(target)
        secure_file(target)
    finally:
        if temporary.exists():
            temporary.unlink()

    return ExportResult(
        playlist_id=playlist_id,
        title=title,
        format=export_format,
        path=str(target),
        track_count=len(tracks),
        bytes_written=len(content.encode("utf-8")),
        truncated=truncated,
    )
