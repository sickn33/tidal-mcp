"""Private, short-lived approval records for remote write operations."""

from __future__ import annotations

import os
import re
import secrets
import tempfile
from datetime import UTC, datetime, timedelta
from pathlib import Path

from tidal_mcp.config import ensure_private_directory, secure_file
from tidal_mcp.exceptions import DraftError
from tidal_mcp.models import ActionDraftRecord, MutationResult

TOKEN_PATTERN = re.compile(r"^[A-Za-z0-9_-]{32,128}$")


class DraftStore:
    """Persist approval drafts atomically with owner-only permissions."""

    def __init__(self, root: Path, ttl_seconds: int) -> None:
        self.root = root
        self.ttl_seconds = ttl_seconds

    def create_action(
        self,
        *,
        action: str,
        payload: dict[str, object],
        preview: dict[str, object],
        destructive: bool,
    ) -> ActionDraftRecord:
        now = datetime.now(UTC)
        record = ActionDraftRecord(
            approval_token=secrets.token_urlsafe(32),
            action=action,
            payload=payload,
            preview=preview,
            destructive=destructive,
            created_at=now.isoformat(),
            expires_at=(now + timedelta(seconds=self.ttl_seconds)).isoformat(),
        )
        self.save_action(record)
        return record

    def load_action(
        self,
        approval_token: str,
        *,
        allow_expired: bool = False,
    ) -> ActionDraftRecord:
        path = self._path(approval_token)
        if not path.exists():
            raise DraftError("Unknown approval token. Create a fresh action preview.")
        try:
            record = ActionDraftRecord.model_validate_json(path.read_text(encoding="utf-8"))
        except Exception as exc:
            raise DraftError("The approval draft is unreadable. Create a fresh preview.") from exc
        if not allow_expired and datetime.fromisoformat(record.expires_at) <= datetime.now(UTC):
            raise DraftError("The approval draft expired. Create a fresh action preview.")
        return record

    def save_action(self, record: ActionDraftRecord) -> None:
        self._save_json(record.approval_token, record.model_dump_json(indent=2))

    def _save_json(self, approval_token: str, content: str) -> None:
        ensure_private_directory(self.root)
        destination = self._path(approval_token)
        temporary: Path | None = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="w",
                encoding="utf-8",
                dir=self.root,
                prefix=".draft-",
                suffix=".tmp",
                delete=False,
            ) as handle:
                handle.write(content)
                handle.flush()
                os.fsync(handle.fileno())
                temporary = Path(handle.name)
            secure_file(temporary)
            os.replace(temporary, destination)
            secure_file(destination)
        finally:
            if temporary is not None and temporary.exists():
                temporary.unlink()

    def claim(self, record: ActionDraftRecord) -> None:
        """Atomically reserve a draft across threads and server processes."""
        ensure_private_directory(self.root)
        claim_path = self._claim_path(record.approval_token)
        try:
            descriptor = os.open(claim_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        except FileExistsError as exc:
            raise DraftError(
                "This draft is already being committed or was interrupted. Inspect TIDAL before "
                "creating a fresh preview."
            ) from exc
        else:
            os.close(descriptor)
            secure_file(claim_path)

    def mark_action_committing(self, record: ActionDraftRecord) -> ActionDraftRecord:
        updated = record.model_copy(update={"state": "committing"})
        self.save_action(updated)
        return updated

    def mark_action_committed(
        self,
        record: ActionDraftRecord,
        result: MutationResult,
    ) -> ActionDraftRecord:
        updated = record.model_copy(update={"state": "committed", "result": result})
        self.save_action(updated)
        return updated

    def mark_action_failed(
        self,
        record: ActionDraftRecord,
        message: str,
    ) -> ActionDraftRecord:
        updated = record.model_copy(update={"state": "failed", "failure_message": message})
        self.save_action(updated)
        return updated

    def _path(self, approval_token: str) -> Path:
        if not TOKEN_PATTERN.fullmatch(approval_token):
            raise DraftError("Invalid approval token format.")
        return self.root / f"{approval_token}.json"

    def _claim_path(self, approval_token: str) -> Path:
        if not TOKEN_PATTERN.fullmatch(approval_token):
            raise DraftError("Invalid approval token format.")
        return self.root / f"{approval_token}.claim"
