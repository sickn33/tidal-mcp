"""Runtime dependency container used by production and tests."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

from tidal_mcp.client import MusicClient, TidalClient
from tidal_mcp.config import Settings
from tidal_mcp.drafts import DraftStore
from tidal_mcp.models import AuthStatus


@dataclass(slots=True)
class Runtime:
    settings: Settings
    client_factory: Callable[[], MusicClient]
    auth_status_checker: Callable[[], AuthStatus]
    draft_store: DraftStore
    _client: MusicClient | None = field(default=None, init=False, repr=False)

    @classmethod
    def from_settings(cls, settings: Settings | None = None) -> Runtime:
        resolved = settings or Settings.from_environment()
        project_dir = Path(__file__).resolve().parents[2]
        login_command = f"uv run --directory {project_dir} tidal-auth"
        return cls(
            settings=resolved,
            client_factory=lambda: TidalClient.from_session_file(resolved.session_file),
            auth_status_checker=lambda: TidalClient.authentication_status(
                resolved.session_file,
                login_command,
            ),
            draft_store=DraftStore(resolved.draft_dir, resolved.draft_ttl_seconds),
        )

    def client(self) -> MusicClient:
        if self._client is None:
            self._client = self.client_factory()
        return self._client

    def auth_status(self) -> AuthStatus:
        return self.auth_status_checker()
