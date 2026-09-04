"""Domain exceptions with safe, model-facing messages."""

from __future__ import annotations

from tidal_mcp.models import CommitPlaylistResult


class TidalMCPError(Exception):
    """Base class for expected local MCP failures."""


class AuthenticationRequiredError(TidalMCPError):
    """Raised when no valid TIDAL session is available."""


class TidalClientError(TidalMCPError):
    """Raised for an expected failure while calling TIDAL."""


class DraftError(TidalMCPError):
    """Raised for invalid, expired, or already-used approval drafts."""


class PartialPlaylistCreationError(TidalClientError):
    """Raised when a playlist exists but adding its tracks failed."""

    def __init__(self, result: CommitPlaylistResult) -> None:
        super().__init__(result.message)
        self.result = result
