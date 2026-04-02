from __future__ import annotations

import base64
import logging
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


def load_gmail_credentials(config: Config) -> Credentials:
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow

    token_path = Path(config.gmail_token_file)
    credentials_path = Path(config.gmail_credentials_file)
    credentials: Credentials | None = None

    if token_path.exists():
        credentials = Credentials.from_authorized_user_file(token_path, SCOPES)

    if credentials and credentials.valid:
        return credentials

    if credentials and credentials.expired and credentials.refresh_token:
        logger.debug("Refreshing cached Gmail OAuth token from %s", token_path)
        credentials.refresh(Request())
    else:
        if not credentials_path.exists():
            raise click.ClickException(
                "Gmail credentials file not found. Provide --gmail-credentials-file / "
                "PCO_GMAIL_CREDENTIALS_FILE with your downloaded OAuth client secrets JSON."
            )
        logger.info("Starting Gmail OAuth flow using credentials from %s", credentials_path)
        flow = InstalledAppFlow.from_client_secrets_file(str(credentials_path), SCOPES)
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
