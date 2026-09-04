"""Interactive authentication kept deliberately outside the MCP protocol."""

from __future__ import annotations

import argparse
import os
import sys
import tempfile
import webbrowser
from concurrent.futures import TimeoutError as FutureTimeoutError
from pathlib import Path

import tidalapi

from tidal_mcp.client import TidalClient
from tidal_mcp.config import Settings, ensure_private_directory, secure_file


def _authorization_url(login: object) -> str:
    value = str(getattr(login, "verification_uri_complete", ""))
    if not value:
        raise RuntimeError("TIDAL did not return an authorization URL")
    return value if value.startswith(("http://", "https://")) else f"https://{value}"


def _save_session_securely(session: tidalapi.Session, destination: Path) -> None:
    ensure_private_directory(destination.parent)
    temporary: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            dir=destination.parent,
            prefix=".session-",
            suffix=".tmp",
            delete=False,
        ) as handle:
            temporary = Path(handle.name)
        secure_file(temporary)
        session.save_session_to_file(temporary)
        secure_file(temporary)
        os.replace(temporary, destination)
        secure_file(destination)
    finally:
        if temporary is not None and temporary.exists():
            temporary.unlink()


def authenticate(settings: Settings, *, open_browser: bool = True) -> int:
    try:
        session = tidalapi.Session()
        login, future = session.login_oauth()
        url = _authorization_url(login)
        print("Open this TIDAL authorization link:")
        print(url)
        if open_browser and not webbrowser.open(url):
            print("The browser did not open automatically; use the link above.", file=sys.stderr)
        expires_in = int(getattr(login, "expires_in", 300))
        future.result(timeout=expires_in + 10)
        if not session.check_login():
            print("TIDAL did not confirm the login.", file=sys.stderr)
            return 1
        _save_session_securely(session, settings.session_file)
        user_id = getattr(session.user, "id", "unknown")
        print(f"TIDAL authentication complete for user {user_id}.")
        print(f"Session saved securely at {settings.session_file}")
        return 0
    except FutureTimeoutError:
        print("The TIDAL authorization link expired. Run tidal-auth again.", file=sys.stderr)
        return 1
    except Exception:
        print("TIDAL authentication failed. No credentials were printed or saved.", file=sys.stderr)
        return 1


def show_status(settings: Settings) -> int:
    status = TidalClient.authentication_status(settings.session_file, "tidal-auth")
    print(status.model_dump_json(indent=2))
    return 0 if status.authenticated else 1


def logout(settings: Settings, *, confirmed: bool) -> int:
    if not confirmed:
        print("Refusing to remove the session without --yes.", file=sys.stderr)
        return 2
    if settings.session_file.exists():
        settings.session_file.unlink()
        print(f"Removed local TIDAL session: {settings.session_file}")
    else:
        print("No local TIDAL session exists.")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Authenticate tidal-local-mcp with TIDAL.")
    parser.add_argument(
        "--no-browser",
        action="store_true",
        help="Print the URL without opening it.",
    )
    parser.add_argument("--status", action="store_true", help="Validate the saved session.")
    parser.add_argument("--logout", action="store_true", help="Remove the saved local session.")
    parser.add_argument("--yes", action="store_true", help="Confirm --logout.")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    settings = Settings.from_environment()
    if args.status and args.logout:
        raise SystemExit("Choose either --status or --logout, not both.")
    if args.status:
        raise SystemExit(show_status(settings))
    if args.logout:
        raise SystemExit(logout(settings, confirmed=args.yes))
    raise SystemExit(authenticate(settings, open_browser=not args.no_browser))
