from __future__ import annotations

import json
import logging

import click

from .client import PCOClient
from .models import Config
from .reporting import build_plan_song_report, find_folders_by_name, format_dt, render_plan_table

BASE_URL = "https://api.planningcenteronline.com"
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
@click.pass_context
def cli(
    ctx: click.Context,
    app_id: str | None,
    secret: str | None,
    token: str | None,
    base_url: str,
    timeout: float,
    verbose: int,
) -> None:
    """Planning Center Services reporting utilities."""
    configure_logging(verbosity=verbose)
    ctx.obj = Config(
        app_id=app_id,
        secret=secret,
        token=token,
        base_url=base_url,
        timeout=timeout,
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
@click.option("--json-output", is_flag=True, help="Emit machine-readable JSON.")
@click.pass_obj
def review_folder(
    config: Config,
    folder_id: str,
    days_ahead: int,
    all_future: bool,
    review_window_years: int,
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
                "sort_date": row.sort_date.isoformat() if row.sort_date else None,
                "song_id": row.song_id,
                "song_title": row.song_title,
                "needs_review": row.needs_review,
                "last_played_at": row.last_played_at.isoformat() if row.last_played_at else None,
                "last_plan_dates": row.last_plan_dates,
                "last_service_type_name": row.last_service_type_name,
                "last_plan_id": row.last_plan_id,
                "last_item_id": row.last_item_id,
            }
            for row in reports
        ]
        click.echo(json.dumps(payload, indent=2))
        return

    if not reports:
        click.echo("No upcoming plans with linked songs found.")
        return

    logger.debug("Printing %d report rows", len(reports))
    plan_groups: list[tuple[tuple[str, str], list]] = []
    for row in reports:
        plan_key = (row.service_type_id, row.plan_id)
        if not plan_groups or plan_groups[-1][0] != plan_key:
            plan_groups.append((plan_key, [row]))
        else:
            plan_groups[-1][1].append(row)

    for index, (_, plan_rows) in enumerate(plan_groups):
        first = plan_rows[0]
        if index > 0:
            click.echo()
        click.echo(
            f"## {format_dt(first.sort_date)} | {first.service_type_name} | "
            f"{first.plan_title} (plan {first.plan_id})"
        )
        click.echo()
        click.echo(render_plan_table(plan_rows))
