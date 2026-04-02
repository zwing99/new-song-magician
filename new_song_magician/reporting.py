from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from functools import lru_cache
from typing import Any

from dateutil import parser as dtparser
from tabulate import tabulate

from .client import PCOClient
from .models import PlanSongReport, SongHistory

IGNORED_SONG_TITLES = {"doxology"}
logger = logging.getLogger(__name__)


def parse_dt(value: str | None) -> datetime | None:
    if not value:
        return None
    dt = dtparser.isoparse(value)
    if dt.tzinfo is None:
        return dt.replace(tzinfo=UTC)
    return dt


def format_dt(value: datetime | None) -> str:
    if value is None:
        return "never"
    return value.astimezone(UTC).strftime("%Y-%m-%d")


def normalize_song_title(song: dict[str, Any]) -> str:
    attrs = song.get("attributes", {})
    return attrs.get("title") or attrs.get("name") or f"Song {song.get('id')}"


def should_ignore_song(song_title: str) -> bool:
    return song_title.strip().casefold() in IGNORED_SONG_TITLES


def render_plan_table(rows: list[PlanSongReport]) -> str:
    table_rows: list[dict[str, str]] = []

    for row in rows:
        if row.needs_review:
            status = "REVIEW"
            last_scheduled = (
                "never scheduled in folder"
                if row.last_played_at is None
                else format_dt(row.last_played_at)
            )
        else:
            status = "OK"
            played_in = row.last_service_type_name or "unknown service type"
            played_on = row.last_plan_dates or format_dt(row.last_played_at)
            last_scheduled = f"{played_on} ({played_in})"

        table_rows.append(
            {
                "Status": status,
                "Song": row.song_title,
                "Song ID": row.song_id,
                "Last Scheduled": last_scheduled,
            }
        )

    return tabulate(table_rows, headers="keys", tablefmt="github", disable_numparse=True)


def find_folders_by_name(
    api: PCOClient,
    target_name: str,
    *,
    exact: bool,
    case_sensitive: bool,
) -> list[dict[str, str]]:
    matches: list[dict[str, str]] = []
    logger.debug("Looking up folders matching %r", target_name)

    for folder in api.paginate("/services/v2/folders"):
        attrs = folder.get("attributes", {})
        folder_name = attrs.get("name", "")
        folder_id = folder.get("id", "")

        lhs = folder_name if case_sensitive else folder_name.lower()
        rhs = target_name if case_sensitive else target_name.lower()
        matched = lhs == rhs if exact else rhs in lhs

        if matched:
            matches.append({"id": folder_id, "name": folder_name})

    matches.sort(key=lambda item: (item["name"].lower(), item["id"]))
    return matches


def get_folder_service_types(api: PCOClient, folder_id: str) -> list[dict[str, Any]]:
    logger.debug("Fetching service types for folder %s", folder_id)
    return list(api.paginate(f"/services/v2/folders/{folder_id}/service_types"))


def get_upcoming_plans(
    api: PCOClient,
    service_type_id: str,
    *,
    days_ahead: int | None,
    all_future: bool,
) -> list[dict[str, Any]]:
    params: dict[str, Any] = {"filter": "future", "order": "sort_date"}

    if not all_future and days_ahead is not None:
        now = datetime.now(UTC).replace(microsecond=0)
        params["after"] = now.isoformat()
        params["before"] = (now + timedelta(days=days_ahead)).isoformat()

    logger.debug("Fetching upcoming plans for service type %s", service_type_id)
    return list(api.paginate(f"/services/v2/service_types/{service_type_id}/plans", params=params))


def get_plan_items_with_songs(
    api: PCOClient,
    service_type_id: str,
    plan_id: str,
) -> tuple[list[dict[str, Any]], dict[str, dict[str, Any]]]:
    logger.debug("Fetching items for plan %s in service type %s", plan_id, service_type_id)
    payload = api.get_json(
        f"/services/v2/service_types/{service_type_id}/plans/{plan_id}/items",
        params={"include": "song", "per_page": 100},
    )

    items = list(payload.get("data", []))
    songs_by_id: dict[str, dict[str, Any]] = {}

    for included in payload.get("included", []):
        if included.get("type") == "Song" and included.get("id"):
            songs_by_id[included["id"]] = included

    meta = payload.get("meta", {}) or {}
    total = meta.get("count", len(items))
    offset = len(items)

    while offset < total:
        next_payload = api.get_json(
            f"/services/v2/service_types/{service_type_id}/plans/{plan_id}/items",
            params={"include": "song", "per_page": 100, "offset": offset},
        )
        next_items = next_payload.get("data", [])
        items.extend(next_items)

        for included in next_payload.get("included", []):
            if included.get("type") == "Song" and included.get("id"):
                songs_by_id[included["id"]] = included

        if not next_items:
            break
        offset += len(next_items)

    return items, songs_by_id


def extract_real_song_ids(items: list[dict[str, Any]]) -> list[str]:
    song_ids: list[str] = []
    seen: set[str] = set()

    for item in items:
        attrs = item.get("attributes", {})
        if attrs.get("item_type") != "song":
            continue

        rel = item.get("relationships", {}).get("song", {}).get("data")
        song_id = rel.get("id") if rel else None
        if not song_id or song_id in seen:
            continue

        seen.add(song_id)
        song_ids.append(song_id)

    return song_ids


def get_last_song_history_before(
    api: PCOClient,
    song_id: str,
    before: datetime,
    current_plan_id: str,
    allowed_service_type_ids: set[str],
) -> SongHistory:
    for history in get_song_history_candidates_before(
        api,
        song_id,
        before,
        allowed_service_type_ids,
    ):
        if history.last_plan_id == current_plan_id:
            logger.debug(
                "Skipping current plan schedule for song %s in plan %s",
                song_id,
                history.last_plan_id,
            )
            continue
        return history

    return SongHistory(None, None, None, None, None)


def get_song_history_candidates_before(
    api: PCOClient,
    song_id: str,
    before: datetime,
    allowed_service_type_ids: set[str],
) -> tuple[SongHistory, ...]:
    logger.debug(
        "Fetching prior schedule candidates for song %s before %s",
        song_id,
        format_dt(before),
    )
    histories: list[SongHistory] = []
    for row in api.paginate(
        f"/services/v2/songs/{song_id}/song_schedules",
        params={
            "filter": "before",
            "before": before.isoformat(),
            "per_page": 100,
            "order": "-plan_sort_date",
        },
    ):
        rels = row.get("relationships", {})
        row_plan_id = ((rels.get("plan") or {}).get("data") or {}).get("id")
        row_service_type_id = ((rels.get("service_type") or {}).get("data") or {}).get("id")
        if row_service_type_id not in allowed_service_type_ids:
            logger.debug(
                "Skipping schedule for song %s in service type %s outside folder scope",
                song_id,
                row_service_type_id,
            )
            continue

        attrs = row.get("attributes", {})
        histories.append(
            SongHistory(
                last_played_at=parse_dt(attrs.get("plan_sort_date")),
                last_plan_dates=attrs.get("plan_dates"),
                last_service_type_name=attrs.get("service_type_name"),
                last_plan_id=row_plan_id,
                last_item_id=((rels.get("item") or {}).get("data") or {}).get("id"),
            )
        )

    return tuple(histories)


def build_plan_song_report(
    api: PCOClient,
    folder_id: str,
    *,
    days_ahead: int | None,
    all_future: bool,
    review_window_years: int,
) -> list[PlanSongReport]:
    service_types = get_folder_service_types(api, folder_id)
    folder_service_type_ids = {service_type["id"] for service_type in service_types}
    candidate_plans: list[tuple[datetime | None, dict[str, Any], dict[str, Any]]] = []
    report_now = datetime.now(UTC).replace(microsecond=0)
    logger.debug("Found %d service types in folder %s", len(service_types), folder_id)

    for service_type in service_types:
        service_type_id = service_type["id"]
        for plan in get_upcoming_plans(
            api,
            service_type_id,
            days_ahead=days_ahead,
            all_future=all_future,
        ):
            sort_date = parse_dt(plan.get("attributes", {}).get("sort_date"))
            candidate_plans.append((sort_date, service_type, plan))

    candidate_plans.sort(
        key=lambda item: (
            item[0] is None,
            item[0] or datetime.max.replace(tzinfo=UTC),
        )
    )

    reports: list[PlanSongReport] = []
    logger.debug("Found %d upcoming plans to inspect", len(candidate_plans))

    @lru_cache(maxsize=512)
    def get_cached_song_history_candidates(song_id: str) -> tuple[SongHistory, ...]:
        logger.debug("Resolving cached history candidates for song %s", song_id)
        return get_song_history_candidates_before(
            api,
            song_id,
            report_now,
            allowed_service_type_ids=folder_service_type_ids,
        )

    for plan_dt, service_type, plan in candidate_plans:
        if plan_dt is None:
            continue

        service_type_id = service_type["id"]
        service_type_name = service_type.get("attributes", {}).get(
            "name", f"Service Type {service_type_id}"
        )
        plan_id = plan["id"]
        plan_title = plan.get("attributes", {}).get("title") or f"Plan {plan_id}"
        logger.debug(
            "Reviewing plan %s (%s) on %s",
            plan_title,
            plan_id,
            format_dt(plan_dt),
        )

        items, songs_by_id = get_plan_items_with_songs(api, service_type_id, plan_id)
        cutoff = report_now - timedelta(days=review_window_years * 365)

        for song_id in extract_real_song_ids(items):
            song_obj = songs_by_id.get(song_id, {"id": song_id, "attributes": {}})
            song_title = normalize_song_title(song_obj)
            if should_ignore_song(song_title):
                logger.debug("Skipping ignored song %r in plan %s", song_title, plan_id)
                continue

            history_candidates = get_cached_song_history_candidates(song_id)
            history = next(
                (
                    candidate
                    for candidate in history_candidates
                    if candidate.last_plan_id != plan_id
                ),
                SongHistory(None, None, None, None, None),
            )

            last_played_at = history.last_played_at
            needs_review = last_played_at is None or last_played_at < cutoff

            reports.append(
                PlanSongReport(
                    service_type_id=service_type_id,
                    service_type_name=service_type_name,
                    plan_id=plan_id,
                    plan_title=plan_title,
                    sort_date=plan_dt,
                    song_id=song_id,
                    song_title=song_title,
                    needs_review=needs_review,
                    last_played_at=last_played_at,
                    last_plan_dates=history.last_plan_dates,
                    last_service_type_name=history.last_service_type_name,
                    last_plan_id=history.last_plan_id,
                    last_item_id=history.last_item_id,
                )
            )

    logger.debug("Built %d plan-song report rows", len(reports))
    return reports
