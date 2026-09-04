from __future__ import annotations

import importlib
import runpy
import sys
from concurrent.futures import TimeoutError as FutureTimeoutError
from pathlib import Path
from types import SimpleNamespace

import pytest

from tidal_mcp import auth_cli
from tidal_mcp.config import Settings


class LoginFuture:
    def __init__(self, error: Exception | None = None) -> None:
        self.error = error

    def result(self, *, timeout: int) -> None:
        assert timeout == 310
        if self.error is not None:
            raise self.error


class LoginSession:
    def __init__(self, *, authenticated: bool = True, error: Exception | None = None) -> None:
        self.authenticated = authenticated
        self.error = error
        self.user = SimpleNamespace(id="user-1")

    def login_oauth(self) -> tuple[SimpleNamespace, LoginFuture]:
        login = SimpleNamespace(
            verification_uri_complete="https://login.tidal.com/fixture",
            expires_in=300,
        )
        return login, LoginFuture(self.error)

    def check_login(self) -> bool:
        return self.authenticated

    def save_session_to_file(self, path: Path) -> None:
        path.write_text("fixture session", encoding="utf-8")


def settings(tmp_path: Path) -> Settings:
    return Settings(
        data_dir=tmp_path,
        session_file=tmp_path / "session.json",
        writes_enabled=False,
        draft_ttl_seconds=900,
    )


def test_authenticate_saves_a_valid_session(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr(auth_cli.tidalapi, "Session", LoginSession)
    monkeypatch.setattr(auth_cli.webbrowser, "open", lambda _: True)
    result = auth_cli.authenticate(settings(tmp_path))
    assert result == 0
    assert (tmp_path / "session.json").read_text(encoding="utf-8") == "fixture session"
    assert "authentication complete" in capsys.readouterr().out


def test_authenticate_handles_expiry_without_saving(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr(
        auth_cli.tidalapi,
        "Session",
        lambda: LoginSession(error=FutureTimeoutError()),
    )
    result = auth_cli.authenticate(settings(tmp_path), open_browser=False)
    assert result == 1
    assert not (tmp_path / "session.json").exists()
    assert "expired" in capsys.readouterr().err


def test_authenticate_requires_confirmed_login(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr(auth_cli.tidalapi, "Session", lambda: LoginSession(authenticated=False))
    result = auth_cli.authenticate(settings(tmp_path), open_browser=False)
    assert result == 1
    assert "did not confirm" in capsys.readouterr().err


def test_status_and_logout_are_safe(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    resolved = settings(tmp_path)
    assert auth_cli.show_status(resolved) == 1
    assert '"authenticated": false' in capsys.readouterr().out
    resolved.session_file.write_text("fixture", encoding="utf-8")
    assert auth_cli.logout(resolved, confirmed=False) == 2
    assert resolved.session_file.exists()
    assert auth_cli.logout(resolved, confirmed=True) == 0
    assert not resolved.session_file.exists()


def test_parser_exposes_noninteractive_operations() -> None:
    parser = auth_cli.build_parser()
    arguments = parser.parse_args(["--status"])
    assert arguments.status is True
    assert arguments.logout is False


def test_authorization_and_session_save_failures_are_safe(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    with pytest.raises(RuntimeError, match="authorization URL"):
        auth_cli._authorization_url(SimpleNamespace())

    class FailingSave:
        def save_session_to_file(self, _path: Path) -> None:
            raise RuntimeError("private")

    with pytest.raises(RuntimeError):
        auth_cli._save_session_securely(FailingSave(), tmp_path / "private" / "session.json")
    assert list((tmp_path / "private").glob(".session-*.tmp")) == []


def test_authenticate_reports_browser_and_generic_failures(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr(auth_cli.tidalapi, "Session", LoginSession)
    monkeypatch.setattr(auth_cli.webbrowser, "open", lambda _: False)
    assert auth_cli.authenticate(settings(tmp_path)) == 0
    assert "did not open" in capsys.readouterr().err

    monkeypatch.setattr(
        auth_cli.tidalapi,
        "Session",
        lambda: (_ for _ in ()).throw(RuntimeError("private")),
    )
    assert auth_cli.authenticate(settings(tmp_path)) == 1
    assert "failed" in capsys.readouterr().err


def test_status_success_and_logout_when_already_absent(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    resolved = settings(tmp_path)
    monkeypatch.setattr(
        auth_cli.TidalClient,
        "authentication_status",
        lambda *_args: SimpleNamespace(
            authenticated=True,
            model_dump_json=lambda **_kwargs: '{"authenticated": true}',
        ),
    )
    assert auth_cli.show_status(resolved) == 0
    assert auth_cli.logout(resolved, confirmed=True) == 0
    assert "No local" in capsys.readouterr().out


@pytest.mark.parametrize(
    ("argv", "expected"),
    [
        (["tidal-auth", "--status", "--logout"], "Choose either --status or --logout, not both."),
        (["tidal-auth", "--status"], 7),
        (["tidal-auth", "--logout", "--yes"], 8),
        (["tidal-auth", "--no-browser"], 9),
    ],
)
def test_main_routes_cli_modes(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    argv: list[str],
    expected: object,
) -> None:
    monkeypatch.setattr(sys, "argv", argv)
    monkeypatch.setattr(auth_cli.Settings, "from_environment", lambda: settings(tmp_path))
    monkeypatch.setattr(auth_cli, "show_status", lambda _settings: 7)
    monkeypatch.setattr(auth_cli, "logout", lambda _settings, *, confirmed: 8 if confirmed else 2)
    monkeypatch.setattr(
        auth_cli,
        "authenticate",
        lambda _settings, *, open_browser: 1 if open_browser else 9,
    )
    with pytest.raises(SystemExit) as caught:
        auth_cli.main()
    assert caught.value.code == expected


def test_module_entrypoint_calls_server_main(monkeypatch: pytest.MonkeyPatch) -> None:
    import tidal_mcp.server

    called: list[bool] = []
    monkeypatch.setattr(tidal_mcp.server, "main", lambda: called.append(True))
    importlib.import_module("tidal_mcp.__main__")
    with pytest.warns(RuntimeWarning, match="found in sys.modules"):
        runpy.run_module("tidal_mcp.__main__", run_name="__main__")
    assert called == [True]
