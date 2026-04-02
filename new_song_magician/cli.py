from __future__ import annotations

import json
import logging

import click

from .client import PCOClient
from .gmail import send_report_email
from .models import Config
from .reporting import (
    arrangement_url,
    build_plan_song_report,
    find_folders_by_name,
    folder_dashboard_url,
    plan_url,
    render_full_report_html,
    render_full_report_markdown,
    song_url,
)

BASE_URL = "https://api.planningcenteronline.com"
DEFAULT_GMAIL_CREDENTIALS_FILE = "gmail-oauth-client-secret.json"
DEFAULT_GMAIL_TOKEN_FILE = ".gmail-token.json"
logger = logging.getLogger(__name__)


def configure_logging(*, verbosity: int) -> None:
    level = logging.WARNING
    if verbosity == 1:
        level = logging.INFO
    elif verbosity >= 2:
        level = logging.DEBUG
    logging.basicConfig(level=level)


@click.group(context_settings={"auto_envvar_prefix": "PCO"})
@click.option("--app-id", envvar="PCO_APP_ID", help="Planning Center application ID.")
@click.option("--secret", envvar="PCO_SECRET", help="Planning Center application secret.")
@click.option("--token", envvar="PCO_TOKEN", help="Planning Center bearer token.")
@click.option(
    "--base-url",
    default=BASE_URL,
    show_default=True,
    envvar="PCO_BASE_URL",
    help="Base API URL.",
)
@click.option(
    "--timeout",
    type=float,
    default=30.0,
    show_default=True,
    envvar="PCO_TIMEOUT",
    help="HTTP timeout in seconds.",
)
@click.option(
    "-v",
    "--verbose",
    count=True,
    help="Increase logging verbosity. Use -v for INFO and -vv for DEBUG.",
)
@click.option(
    "--gmail-credentials-file",
    default=DEFAULT_GMAIL_CREDENTIALS_FILE,
    show_default=True,
    envvar="PCO_GMAIL_CREDENTIALS_FILE",
    help="Google OAuth client secrets JSON used when sending Gmail messages.",
)
@click.option(
    "--gmail-token-file",
    default=DEFAULT_GMAIL_TOKEN_FILE,
    show_default=True,
    envvar="PCO_GMAIL_TOKEN_FILE",
    help="Path for the cached Gmail OAuth token JSON.",
)
@click.option(
    "--gmail-from",
    envvar="PCO_GMAIL_FROM",
    help="Optional From header to use for Gmail messages.",
)
@click.pass_context
def cli(
    ctx: click.Context,
    app_id: str | None,
    secret: str | None,
    token: str | None,
    base_url: str,
    timeout: float,
    verbose: int,
    gmail_credentials_file: str,
    gmail_token_file: str,
    gmail_from: str | None,
) -> None:
    """Planning Center Services reporting utilities."""
    configure_logging(verbosity=verbose)
    ctx.obj = Config(
        app_id=app_id,
        secret=secret,
        token=token,
        base_url=base_url,
        timeout=timeout,
        gmail_credentials_file=gmail_credentials_file,
        gmail_token_file=gmail_token_file,
        gmail_from=gmail_from,
    )


@cli.command("lookup-folder")
@click.argument("name", envvar="PCO_LOOKUP_FOLDER_NAME")
@click.option("--exact/--contains", default=True, show_default=True)
@click.option("--case-sensitive/--ignore-case", default=False, show_default=True)
@click.option("--json-output", is_flag=True, help="Emit machine-readable JSON.")
@click.pass_obj
def lookup_folder(
    config: Config,
    name: str,
    exact: bool,
    case_sensitive: bool,
    json_output: bool,
) -> None:
    """Look up folder IDs by folder name."""
    logger.debug("Starting folder lookup")
    api = PCOClient(config)
    try:
        matches = find_folders_by_name(
            api,
            name,
            exact=exact,
            case_sensitive=case_sensitive,
        )
    finally:
        api.close()

    if json_output:
        click.echo(json.dumps(matches, indent=2))
        return

    if not matches:
        raise click.ClickException("No matching folders found.")

    logger.debug("Found %d matching folders", len(matches))
    for match in matches:
        click.echo(f"{match['id']}\t{match['name']}")


@cli.command("review-folder")
@click.argument("folder_id", envvar="PCO_REVIEW_FOLDER_FOLDER_ID")
@click.option(
    "--days-ahead",
    type=click.IntRange(min=1),
    default=30,
    show_default=True,
    envvar="PCO_REVIEW_FOLDER_DAYS_AHEAD",
    help="Check plans from now through this many days ahead.",
)
@click.option(
    "--all-future",
    is_flag=True,
    envvar="PCO_REVIEW_FOLDER_ALL_FUTURE",
    help="Check all future plans instead of limiting by --days-ahead.",
)
@click.option(
    "--review-window-years",
    type=click.IntRange(min=1),
    default=3,
    show_default=True,
    envvar="PCO_REVIEW_FOLDER_REVIEW_WINDOW_YEARS",
    help="Flag songs whose previous play is older than this many years.",
)
@click.option(
    "--email",
    "emails",
    multiple=True,
    envvar="PCO_REVIEW_FOLDER_EMAILS",
    help=(
        "Send the report via Gmail to this address. Repeat the flag as needed. "
        "The env var accepts a whitespace-separated list."
    ),
)
@click.option(
    "--print/--no-print",
    "print_output",
    default=True,
    show_default=True,
    help="Print the report to stdout.",
)
@click.option("--json-output", is_flag=True, help="Emit machine-readable JSON.")
@click.pass_obj
def review_folder(
    config: Config,
    folder_id: str,
    days_ahead: int,
    all_future: bool,
    review_window_years: int,
    emails: tuple[str, ...],
    print_output: bool,
    json_output: bool,
) -> None:
    """Report upcoming plan songs and whether they need review."""
    logger.debug("Starting review report for folder %s", folder_id)
    api = PCOClient(config)
    try:
        reports = build_plan_song_report(
            api,
            folder_id=folder_id,
            days_ahead=None if all_future else days_ahead,
            all_future=all_future,
            review_window_years=review_window_years,
        )
    finally:
        api.close()

    if json_output:
        payload = [
            {
                "service_type_id": row.service_type_id,
                "service_type_name": row.service_type_name,
                "plan_id": row.plan_id,
                "plan_title": row.plan_title,
                "plan_url": plan_url(row.plan_id),
                "sort_date": row.sort_date.isoformat() if row.sort_date else None,
                "song_id": row.song_id,
                "song_title": row.song_title,
                "arrangement_id": row.arrangement_id,
                "arrangement_name": row.arrangement_name,
                "arrangement_url": (
                    arrangement_url(row.song_id, row.arrangement_id) if row.arrangement_id else None
                ),
                "key_name": row.key_name,
                "song_url": song_url(row.song_id),
                "needs_review": row.needs_review,
                "last_played_at": row.last_played_at.isoformat() if row.last_played_at else None,
                "last_plan_dates": row.last_plan_dates,
                "last_service_type_name": row.last_service_type_name,
                "last_plan_id": row.last_plan_id,
                "last_plan_url": plan_url(row.last_plan_id) if row.last_plan_id else None,
                "last_item_id": row.last_item_id,
                "folder_url": folder_dashboard_url(folder_id),
            }
            for row in reports
        ]
        if print_output:
            click.echo(json.dumps(payload, indent=2))
        return

    report_markdown = render_full_report_markdown(reports)
    if print_output:
        click.echo(report_markdown)

    if emails:
        send_report_email(
            config,
            emails,
            subject=f"New Song Magician report for folder {folder_id}",
            text_body=report_markdown,
            html_body=render_full_report_html(reports, folder_id=folder_id),
        )
