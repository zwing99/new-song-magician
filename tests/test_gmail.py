from __future__ import annotations

import sys
import webbrowser
from pathlib import Path

import click
import pytest

import new_song_magician.gmail as gmail
from new_song_magician.models import Config


def make_config(tmp_path: Path) -> Config:
    return Config(
        app_id="app-id",
        secret="secret",
        token=None,
        base_url="https://api.planningcenteronline.com",
        timeout=30.0,
        gmail_credentials_file=str(tmp_path / "gmail-client-secret.json"),
        gmail_token_file=str(tmp_path / "gmail-token.json"),
        gmail_from="Worship Team <worship@example.com>",
    )


def test_load_gmail_credentials_requires_client_secrets_file(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    config = make_config(tmp_path)
    monkeypatch.delenv("GMAIL_CLIENT", raising=False)
    monkeypatch.delenv("GMAIL_SECRET", raising=False)

    with pytest.raises(click.ClickException) as exc_info:
        gmail.load_gmail_credentials(config)

    assert "Gmail credentials are unavailable" in str(exc_info.value)


@pytest.fixture
def fake_installed_app_flow(monkeypatch: pytest.MonkeyPatch) -> dict[str, object]:
    captured: dict[str, object] = {}

    class FakeFlow:
        def run_local_server(self, **kwargs) -> object:
            captured.setdefault("calls", []).append(dict(kwargs))

            class FakeCredentials:
                valid = True

                def to_json(self) -> str:
                    return '{"token": "token-value"}'

            return FakeCredentials()

    class FakeInstalledAppFlow:
        @staticmethod
        def from_client_config(client_config, scopes):
            captured["client_config"] = client_config
            captured["scopes"] = scopes
            return FakeFlow()

    monkeypatch.setitem(
        sys.modules,
        "google_auth_oauthlib.flow",
        type(
            "FakeGoogleAuthFlowModule",
            (),
            {"InstalledAppFlow": FakeInstalledAppFlow},
        )(),
    )
    return captured


def test_load_gmail_credentials_uses_env_fallback_when_credentials_file_missing(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    fake_installed_app_flow: dict[str, object],
) -> None:
    config = make_config(tmp_path)

    monkeypatch.setenv("GMAIL_CLIENT", "client-id")
    monkeypatch.setenv("GMAIL_SECRET", "client-secret")

    credentials = gmail.load_gmail_credentials(config)

    assert credentials.valid is True
    assert fake_installed_app_flow["calls"] == [{"port": 0}]
    assert fake_installed_app_flow["scopes"] == gmail.SCOPES
    assert fake_installed_app_flow["client_config"] == {
        "installed": {
            "client_id": "client-id",
            "client_secret": "client-secret",
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "redirect_uris": ["http://localhost"],
        }
    }
    assert Path(config.gmail_token_file).read_text(encoding="utf-8") == '{"token": "token-value"}'


def test_load_gmail_credentials_uses_env_fallback_when_credentials_file_empty(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    fake_installed_app_flow: dict[str, object],
) -> None:
    config = make_config(tmp_path)
    Path(config.gmail_credentials_file).write_text("", encoding="utf-8")

    monkeypatch.setenv("GMAIL_CLIENT", "client-id")
    monkeypatch.setenv("GMAIL_SECRET", "client-secret")

    gmail.load_gmail_credentials(config)

    assert fake_installed_app_flow["calls"] == [{"port": 0}]


def test_load_gmail_credentials_ignores_empty_token_and_reauths(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    fake_installed_app_flow: dict[str, object],
) -> None:
    config = make_config(tmp_path)
    Path(config.gmail_token_file).write_text("", encoding="utf-8")
    Path(config.gmail_credentials_file).write_text(
        '{"installed": {"client_id": "client-id", "client_secret": "client-secret"}}',
        encoding="utf-8",
    )

    gmail.load_gmail_credentials(config)

    assert fake_installed_app_flow["calls"] == [{"port": 0}]


def test_load_gmail_credentials_falls_back_to_manual_auth_when_browser_unavailable(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    config = make_config(tmp_path)
    Path(config.gmail_credentials_file).write_text(
        '{"installed": {"client_id": "client-id", "client_secret": "client-secret"}}',
        encoding="utf-8",
    )
    calls: list[dict[str, object]] = []

    class FakeFlow:
        def run_local_server(self, **kwargs) -> object:
            calls.append(dict(kwargs))
            if len(calls) == 1:
                raise webbrowser.Error("could not locate runnable browser")

            class FakeCredentials:
                valid = True

                def to_json(self) -> str:
                    return '{"token": "token-value"}'

            return FakeCredentials()

    class FakeInstalledAppFlow:
        @staticmethod
        def from_client_config(client_config, scopes):
            return FakeFlow()

    monkeypatch.setitem(
        sys.modules,
        "google_auth_oauthlib.flow",
        type(
            "FakeGoogleAuthFlowModule",
            (),
            {"InstalledAppFlow": FakeInstalledAppFlow},
        )(),
    )

    credentials = gmail.load_gmail_credentials(config)

    assert credentials.valid is True
    assert calls == [{"port": 0}, {"port": 0, "open_browser": False}]


def test_send_report_email_builds_gmail_message(monkeypatch, tmp_path: Path) -> None:
    config = make_config(tmp_path)
    sent_messages: list[dict[str, object]] = []

    class FakeSendCall:
        def execute(self) -> dict[str, str]:
            return {"id": "message-1"}

    class FakeMessagesResource:
        def send(self, *, userId: str, body: dict[str, str]) -> FakeSendCall:
            sent_messages.append({"userId": userId, "body": body})
            return FakeSendCall()

    class FakeUsersResource:
        def messages(self) -> FakeMessagesResource:
            return FakeMessagesResource()

    class FakeService:
        def users(self) -> FakeUsersResource:
            return FakeUsersResource()

    monkeypatch.setattr(gmail, "load_gmail_credentials", lambda config: object())
    monkeypatch.setattr(gmail, "_build_gmail_service", lambda credentials: FakeService())
    monkeypatch.setattr(gmail, "_gmail_http_error", lambda: RuntimeError)

    gmail.send_report_email(
        config,
        ("a@example.com", "b@example.com"),
        subject="Subject line",
        text_body="Plain body",
        html_body="<p>HTML body</p>",
    )

    assert sent_messages
    assert sent_messages[0]["userId"] == "me"
    raw_message = str(sent_messages[0]["body"]["raw"])
    assert raw_message
