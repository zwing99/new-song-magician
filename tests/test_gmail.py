from __future__ import annotations

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


def test_load_gmail_credentials_requires_client_secrets_file(tmp_path: Path) -> None:
    config = make_config(tmp_path)

    with pytest.raises(click.ClickException) as exc_info:
        gmail.load_gmail_credentials(config)

    assert "Gmail credentials file not found" in str(exc_info.value)


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
