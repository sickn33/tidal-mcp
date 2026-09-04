"""Run the production MCP tool surface against deterministic read-only fixtures."""

from __future__ import annotations

import tempfile
from pathlib import Path

from tests.fakes import FakeMusicClient
from tidal_mcp.config import Settings
from tidal_mcp.drafts import DraftStore
from tidal_mcp.models import AuthStatus
from tidal_mcp.runtime import Runtime
from tidal_mcp.server import create_server

_temporary_directory = tempfile.TemporaryDirectory(prefix="tidal-mcp-evaluation-")
_root = Path(_temporary_directory.name)
_settings = Settings(
    data_dir=_root,
    session_file=_root / "session.json",
    writes_enabled=False,
    draft_ttl_seconds=900,
)
_fixture_client = FakeMusicClient()
_runtime = Runtime(
    settings=_settings,
    client_factory=lambda: _fixture_client,
    auth_status_checker=lambda: AuthStatus(
        authenticated=True,
        message="Fixture session is valid.",
        session_file=str(_settings.session_file),
        user_id="fixture-user",
        username="fixture",
        login_command="tidal-auth",
    ),
    draft_store=DraftStore(_settings.draft_dir, _settings.draft_ttl_seconds),
)
mcp = create_server(_runtime)


if __name__ == "__main__":
    mcp.run()
