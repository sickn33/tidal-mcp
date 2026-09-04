"""Environment-backed configuration and private local storage paths."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from platformdirs import user_data_path

TRUE_VALUES = {"1", "true", "yes", "on"}


def _env_bool(name: str, default: bool = False) -> bool:
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() in TRUE_VALUES


def _env_int(name: str, default: int, *, minimum: int, maximum: int) -> int:
    value = os.environ.get(name)
    if value is None:
        return default
    try:
        parsed = int(value)
    except ValueError as exc:
        raise ValueError(f"{name} must be an integer") from exc
    if not minimum <= parsed <= maximum:
        raise ValueError(f"{name} must be between {minimum} and {maximum}")
    return parsed


@dataclass(frozen=True, slots=True)
class Settings:
    """Runtime settings for the local MCP server."""

    data_dir: Path
    session_file: Path
    writes_enabled: bool = False
    draft_ttl_seconds: int = 900

    @classmethod
    def from_environment(cls) -> Settings:
        data_dir_value = os.environ.get("TIDAL_MCP_DATA_DIR")
        data_dir = (
            Path(data_dir_value).expanduser()
            if data_dir_value
            else Path(user_data_path("tidal-local-mcp", appauthor=False))
        )
        session_value = os.environ.get("TIDAL_MCP_SESSION_FILE")
        session_file = (
            Path(session_value).expanduser() if session_value else data_dir / "session.json"
        )
        return cls(
            data_dir=data_dir,
            session_file=session_file,
            writes_enabled=_env_bool("TIDAL_MCP_ENABLE_WRITES"),
            draft_ttl_seconds=_env_int(
                "TIDAL_MCP_DRAFT_TTL_SECONDS",
                900,
                minimum=60,
                maximum=3600,
            ),
        )

    @property
    def draft_dir(self) -> Path:
        return self.data_dir / "drafts"


def ensure_private_directory(path: Path) -> Path:
    """Create a local data directory privately without chmod-ing an existing parent."""
    existed = path.exists()
    path.mkdir(parents=True, exist_ok=True, mode=0o700)
    if not existed:
        path.chmod(0o700)
    return path


def secure_file(path: Path) -> None:
    """Force a file containing credentials or approvals to owner-only access."""
    path.chmod(0o600)
