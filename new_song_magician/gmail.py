from __future__ import annotations

import base64
import json
import logging
import os
from email.message import EmailMessage
from pathlib import Path
from typing import TYPE_CHECKING

import click

from .models import Config

SCOPES = ["https://www.googleapis.com/auth/gmail.send"]
logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from google.oauth2.credentials import Credentials


def _build_gmail_service(credentials: Credentials):
    from googleapiclient.discovery import build

    return build("gmail", "v1", credentials=credentials)


def _gmail_http_error() -> type[Exception]:
    from googleapiclient.errors import HttpError

    return HttpError


def _load_cached_gmail_credentials(token_path: Path, scopes: list[str]) -> Credentials | None:
    from google.oauth2.credentials import Credentials

    if not token_path.exists():
        return None

    try:
        token_text = token_path.read_text(encoding="utf-8").strip()
    except OSError as exc:
        raise click.ClickException(f"Unable to read Gmail token file {token_path}: {exc}") from exc

    if not token_text:
        logger.warning("Ignoring empty Gmail token file at %s and starting reauth", token_path)
        return None

    try:
        return Credentials.from_authorized_user_info(json.loads(token_text), scopes)
    except (json.JSONDecodeError, ValueError) as exc:
        logger.warning(
            "Ignoring invalid Gmail token file at %s and starting reauth: %s",
            token_path,
            exc,
        )
        return None


def _gmail_client_config_from_env() -> dict[str, dict[str, object]] | None:
    client_id = os.environ.get("GMAIL_CLIENT", "").strip()
    client_secret = os.environ.get("GMAIL_SECRET", "").strip()
    if not client_id or not client_secret:
        return None

    return {
        "installed": {
            "client_id": client_id,
            "client_secret": client_secret,
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "redirect_uris": ["http://localhost"],
        }
    }


def _load_gmail_client_config(credentials_path: Path) -> dict[str, dict[str, object]]:
    try:
        credentials_text = credentials_path.read_text(encoding="utf-8").strip()
    except OSError:
        credentials_text = ""

    if credentials_text:
        try:
            credentials_data = json.loads(credentials_text)
        except json.JSONDecodeError:
            logger.warning(
                "Ignoring invalid Gmail credentials JSON at %s and trying env fallback",
                credentials_path,
            )
        else:
            if isinstance(credentials_data, dict) and (
                isinstance(credentials_data.get("installed"), dict)
                or isinstance(credentials_data.get("web"), dict)
            ):
                return credentials_data
            logger.warning(
                "Ignoring Gmail credentials file at %s because it is not a Google OAuth client "
                "secrets JSON and trying env fallback",
                credentials_path,
            )
    elif credentials_path.exists():
        logger.warning(
            "Ignoring empty Gmail credentials file at %s and trying env fallback",
            credentials_path,
        )

    env_config = _gmail_client_config_from_env()
    if env_config is not None:
        return env_config

    raise click.ClickException(
        "Gmail credentials are unavailable. Provide a valid --gmail-credentials-file / "
        "PCO_GMAIL_CREDENTIALS_FILE JSON, or set GMAIL_CLIENT and GMAIL_SECRET so the CLI "
        "can start the browser reauth flow."
    )


def load_gmail_credentials(config: Config) -> Credentials:
    from google.auth.transport.requests import Request
    from google_auth_oauthlib.flow import InstalledAppFlow

    token_path = Path(config.gmail_token_file)
    credentials_path = Path(config.gmail_credentials_file)
    credentials = _load_cached_gmail_credentials(token_path, SCOPES)

    if credentials and credentials.valid:
        return credentials

    if credentials and credentials.expired and credentials.refresh_token:
        logger.debug("Refreshing cached Gmail OAuth token from %s", token_path)
        credentials.refresh(Request())
    else:
        client_config = _load_gmail_client_config(credentials_path)
        logger.info("Starting Gmail OAuth flow")
        flow = InstalledAppFlow.from_client_config(client_config, SCOPES)
        credentials = flow.run_local_server(port=0)

    token_path.parent.mkdir(parents=True, exist_ok=True)
    token_path.write_text(credentials.to_json(), encoding="utf-8")
    logger.debug("Saved Gmail OAuth token to %s", token_path)
    return credentials


def send_report_email(
    config: Config,
    recipients: tuple[str, ...],
    *,
    subject: str,
    text_body: str,
    html_body: str,
) -> None:
    if not recipients:
        return

    message = EmailMessage()
    if config.gmail_from:
        message["From"] = config.gmail_from
    message["To"] = ", ".join(recipients)
    message["Subject"] = subject
    message.set_content(text_body)
    message.add_alternative(html_body, subtype="html")

    encoded_message = base64.urlsafe_b64encode(message.as_bytes()).decode("ascii")

    try:
        credentials = load_gmail_credentials(config)
        service = _build_gmail_service(credentials)
        logger.info("Sending Gmail report to %s", ", ".join(recipients))
        service.users().messages().send(userId="me", body={"raw": encoded_message}).execute()
    except _gmail_http_error() as exc:
        raise click.ClickException(f"Gmail API error while sending email: {exc}") from exc
