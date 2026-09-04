from __future__ import annotations

import stat
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from pydantic import ValidationError

from tests.fakes import TRACKS
from tidal_mcp.config import Settings
from tidal_mcp.drafts import DraftStore
from tidal_mcp.exceptions import DraftError
from tidal_mcp.filtering import filter_recommendations
from tidal_mcp.models import MutationResult, RecommendationFilters


def test_settings_are_safe_by_default(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("TIDAL_MCP_DATA_DIR", str(tmp_path))
    monkeypatch.delenv("TIDAL_MCP_ENABLE_WRITES", raising=False)
    settings = Settings.from_environment()
    assert settings.data_dir == tmp_path
    assert settings.session_file == tmp_path / "session.json"
    assert settings.writes_enabled is False
    assert settings.draft_ttl_seconds == 900


def test_explicit_environment_values_are_parsed(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("TIDAL_MCP_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("TIDAL_MCP_SESSION_FILE", str(tmp_path / "custom.json"))
    monkeypatch.setenv("TIDAL_MCP_ENABLE_WRITES", "YES")
    monkeypatch.setenv("TIDAL_MCP_DRAFT_TTL_SECONDS", "60")
    settings = Settings.from_environment()
    assert settings.session_file.name == "custom.json"
    assert settings.writes_enabled is True
    assert settings.draft_ttl_seconds == 60


@pytest.mark.parametrize("value", ["59", "3601", "not-a-number"])
def test_invalid_draft_ttl_is_rejected(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    value: str,
) -> None:
    monkeypatch.setenv("TIDAL_MCP_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("TIDAL_MCP_DRAFT_TTL_SECONDS", value)
    with pytest.raises(ValueError):
        Settings.from_environment()


def test_filter_rejects_unknown_metadata_when_filter_requires_it() -> None:
    unknown = TRACKS["t-1"].model_copy(update={"duration_seconds": None})
    accepted, rejected = filter_recommendations(
        [unknown], RecommendationFilters(duration_seconds_max=300)
    )
    assert accepted == []
    assert rejected == 1


def test_filter_range_validation() -> None:
    with pytest.raises(ValidationError, match="release_year_min"):
        RecommendationFilters(release_year_min=2025, release_year_max=2020)
    with pytest.raises(ValidationError, match="duration_seconds_min"):
        RecommendationFilters(duration_seconds_min=500, duration_seconds_max=100)


def test_filter_all_metadata_rules_and_malformed_years() -> None:
    malformed = TRACKS["t-1"].model_copy(update={"release_date": "badd", "artist_id": None})
    short = TRACKS["t-2"].model_copy(update={"release_date": "20", "artist_id": None})
    accepted, rejected = filter_recommendations(
        [malformed, short, TRACKS["t-3"], TRACKS["t-4"], TRACKS["t-5"]],
        RecommendationFilters(
            release_year_min=2020,
            release_year_max=2024,
            duration_seconds_min=100,
            duration_seconds_max=300,
            explicit=False,
            exclude_track_ids=["t-3"],
        ),
    )
    assert accepted == []
    assert rejected == 5


def test_draft_expiry_and_permissions(tmp_path: Path) -> None:
    store = DraftStore(tmp_path / "drafts", ttl_seconds=60)
    record = store.create_action(
        action="favorite_track",
        payload={"track_ids": ["t-1"]},
        preview={"track": TRACKS["t-1"].model_dump()},
        destructive=False,
    )
    path = store.root / f"{record.approval_token}.json"
    assert stat.S_IMODE(store.root.stat().st_mode) == 0o700
    assert stat.S_IMODE(path.stat().st_mode) == 0o600

    expired = record.model_copy(
        update={"expires_at": (datetime.now(UTC) - timedelta(seconds=1)).isoformat()}
    )
    store.save_action(expired)
    with pytest.raises(DraftError, match="expired"):
        store.load_action(record.approval_token)
    assert store.load_action(record.approval_token, allow_expired=True).action == "favorite_track"


def test_draft_claim_is_atomic_and_private(tmp_path: Path) -> None:
    store = DraftStore(tmp_path / "drafts", ttl_seconds=60)
    record = store.create_action(
        action="favorite_track",
        payload={"track_ids": ["t-1"]},
        preview={},
        destructive=False,
    )
    store.claim(record)
    claim_path = store.root / f"{record.approval_token}.claim"
    assert stat.S_IMODE(claim_path.stat().st_mode) == 0o600
    with pytest.raises(DraftError, match="already being committed"):
        store.claim(record)


def test_existing_parent_permissions_are_not_changed(tmp_path: Path) -> None:
    parent = tmp_path / "existing"
    parent.mkdir(mode=0o755)
    store = DraftStore(parent, ttl_seconds=60)
    store.create_action(action="favorite_track", payload={}, preview={}, destructive=False)
    assert stat.S_IMODE(parent.stat().st_mode) == 0o755


@pytest.mark.parametrize("token", ["../escape", "short", "contains spaces"])
def test_draft_token_cannot_escape_storage(tmp_path: Path, token: str) -> None:
    store = DraftStore(tmp_path / "drafts", ttl_seconds=60)
    with pytest.raises(DraftError, match="Invalid approval token format"):
        store.load_action(token)


def test_action_draft_state_transitions_and_corruption(tmp_path: Path) -> None:
    store = DraftStore(tmp_path / "drafts", ttl_seconds=60)
    record = store.create_action(action="favorite_track", payload={}, preview={}, destructive=False)
    committing = store.mark_action_committing(record)
    result = MutationResult(status="success", action=record.action, message="done")
    store.mark_action_committed(committing, result)
    assert store.load_action(record.approval_token).result == result
    failed = store.mark_action_failed(record, "uncertain")
    assert failed.failure_message == "uncertain"

    path = store.root / f"{record.approval_token}.json"
    path.write_text("not-json", encoding="utf-8")
    with pytest.raises(DraftError, match="unreadable"):
        store.load_action(record.approval_token)
    unknown = "A" * 40
    with pytest.raises(DraftError, match="Unknown"):
        store.load_action(unknown)
    with pytest.raises(DraftError, match="Invalid"):
        store._claim_path("bad")


def test_failed_atomic_save_removes_temporary_file(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    store = DraftStore(tmp_path / "drafts", ttl_seconds=60)
    monkeypatch.setattr(
        "tidal_mcp.drafts.os.replace", lambda *_args: (_ for _ in ()).throw(OSError())
    )
    with pytest.raises(OSError):
        store.create_action(action="favorite_track", payload={}, preview={}, destructive=False)
    assert list(store.root.glob(".draft-*.tmp")) == []
