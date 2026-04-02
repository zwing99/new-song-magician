from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from functools import lru_cache
from html import escape
from typing import Any

from dateutil import parser as dtparser
from tabulate import tabulate

from .client import PCOClient
from .models import PlanSongReport, SongHistory

IGNORED_SONG_TITLES = {"doxology"}
SERVICES_BASE_URL = "https://services.planningcenteronline.com"
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


def folder_dashboard_url(folder_id: str) -> str:
    return f"{SERVICES_BASE_URL}/dashboard/{folder_id}"


def plan_url(plan_id: str) -> str:
    return f"{SERVICES_BASE_URL}/plans/{plan_id}"


def song_url(song_id: str) -> str:
    return f"{SERVICES_BASE_URL}/songs/{song_id}"


def arrangement_url(song_id: str, arrangement_id: str) -> str:
    return f"{SERVICES_BASE_URL}/songs/{song_id}/arrangements/{arrangement_id}"


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
            last_plan_link = ""
        else:
            status = "OK"
            played_in = row.last_service_type_name or "unknown service type"
            played_on = row.last_plan_dates or format_dt(row.last_played_at)
            last_scheduled = f"{played_on} ({played_in})"
            last_plan_link = plan_url(row.last_plan_id) if row.last_plan_id else ""

        table_rows.append(
            {
                "Status": status,
                "Song": row.song_title,
                "Song Link": song_url(row.song_id),
                "Last Scheduled": last_scheduled,
                "Last Plan Link": last_plan_link,
            }
        )

    return tabulate(table_rows, headers="keys", tablefmt="github", disable_numparse=True)


def render_plan_table_html(rows: list[PlanSongReport]) -> str:
    body_rows: list[str] = []

    for row in rows:
        if row.needs_review:
            status = "REVIEW"
            status_bg = "#fff1e8"
            status_fg = "#bc4c00"
            last_scheduled = (
                "never scheduled in folder"
                if row.last_played_at is None
                else format_dt(row.last_played_at)
            )
            last_plan_link = ""
        else:
            status = "OK"
            status_bg = "#e7f6ec"
            status_fg = "#116329"
            played_in = row.last_service_type_name or "unknown service type"
            played_on = row.last_plan_dates or format_dt(row.last_played_at)
            last_scheduled = f"{played_on} ({played_in})"
            last_plan_link = (
                f'<a href="{escape(plan_url(row.last_plan_id))}" '
                'style="color:#0969da;text-decoration:none;font-weight:600;">'
                "Open last plan</a>"
                if row.last_plan_id
                else ""
            )

        last_plan_cell = last_plan_link or '<span style="color:#9ca3af;font-size:13px;">None</span>'
        arrangement_cell = (
            f'<a href="{escape(arrangement_url(row.song_id, row.arrangement_id))}" '
            'style="color:#0969da;text-decoration:none;font-size:13px;font-weight:600;">'
            f"{escape(row.arrangement_name or 'Open arrangement')}</a>"
            if row.arrangement_id
            else '<span style="color:#9ca3af;font-size:13px;">No arrangement linked</span>'
        )
        key_cell = escape(row.key_name or "Unknown key")

        body_rows.append(
            f'<tr style="background:{status_bg if row.needs_review else "#ffffff"};">'
            '<td style="border-top:1px solid #e5e7eb;padding:16px 12px;vertical-align:top;">'
            f'<span style="display:inline-block;background:{status_bg};color:{status_fg};'
            "font-size:12px;font-weight:700;letter-spacing:0.04em;padding:6px 10px;"
            'border-radius:999px;">'
            f"{escape(status)}</span></td>"
            '<td style="border-top:1px solid #e5e7eb;padding:16px 12px;vertical-align:top;">'
            f'<a href="{escape(song_url(row.song_id))}" '
            'style="color:#0969da;text-decoration:none;font-size:16px;font-weight:700;">'
            f"{escape(row.song_title)}</a>"
            f'<div style="margin-top:6px;color:#6b7280;font-size:12px;">Song ID: '
            f"{escape(row.song_id)}</div>"
            '<div style="margin-top:10px;font-size:13px;color:#475467;">Arrangement: '
            f"{arrangement_cell}</div>"
            '<div style="margin-top:4px;font-size:13px;color:#475467;">Scheduled key: '
            f"{key_cell}</div></td>"
            '<td style="border-top:1px solid #e5e7eb;padding:16px 12px;vertical-align:top;">'
            f'<div style="font-size:14px;color:#111827;">{escape(last_scheduled)}</div>'
            "</td>"
            '<td style="border-top:1px solid #e5e7eb;padding:16px 12px;vertical-align:top;">'
            f"{last_plan_cell}"
            "</td>"
            "</tr>"
        )

    return (
        '<table style="border-collapse:separate;border-spacing:0;width:100%;margin:0;'
        'background:#ffffff;border:1px solid #e5e7eb;border-radius:16px;overflow:hidden;">'
        "<thead>"
        "<tr>"
        '<th style="text-align:left;padding:14px 12px;background:#f8fafc;color:#475467;'
        'font-size:12px;letter-spacing:0.04em;text-transform:uppercase;">'
        "Status</th>"
        '<th style="text-align:left;padding:14px 12px;background:#f8fafc;color:#475467;'
        'font-size:12px;letter-spacing:0.04em;text-transform:uppercase;">'
        "Song</th>"
        '<th style="text-align:left;padding:14px 12px;background:#f8fafc;color:#475467;'
        'font-size:12px;letter-spacing:0.04em;text-transform:uppercase;">'
        "Last Scheduled</th>"
        '<th style="text-align:left;padding:14px 12px;background:#f8fafc;color:#475467;'
        'font-size:12px;letter-spacing:0.04em;text-transform:uppercase;">'
        "Last Plan</th>"
        "</tr>"
        "</thead>"
        "<tbody>" + "".join(body_rows) + "</tbody></table>"
    )


def group_plan_rows(
    reports: list[PlanSongReport],
) -> list[tuple[tuple[str, str], list[PlanSongReport]]]:
    plan_groups: list[tuple[tuple[str, str], list[PlanSongReport]]] = []
    for row in reports:
        plan_key = (row.service_type_id, row.plan_id)
        if not plan_groups or plan_groups[-1][0] != plan_key:
            plan_groups.append((plan_key, [row]))
        else:
            plan_groups[-1][1].append(row)
    return plan_groups


def render_full_report_markdown(reports: list[PlanSongReport]) -> str:
    if not reports:
        return "No upcoming plans with linked songs found."

    sections: list[str] = []
    for _, plan_rows in group_plan_rows(reports):
        first = plan_rows[0]
        sections.append(
            f"## {format_dt(first.sort_date)} | {first.service_type_name} | "
            f"{first.plan_title}\n\n"
            f"Plan: {plan_url(first.plan_id)}\n\n"
            f"{render_plan_table(plan_rows)}"
        )
    return "\n\n".join(sections)


def render_full_report_html(reports: list[PlanSongReport], *, folder_id: str) -> str:
    review_count = sum(1 for row in reports if row.needs_review)
    plan_groups = group_plan_rows(reports)

    if not reports:
        body = (
            '<table role="presentation" width="100%" cellpadding="0" cellspacing="0" '
            'style="background:#ffffff;border:1px solid #e5e7eb;border-radius:16px;">'
            '<tr><td style="padding:28px;color:#475467;font-size:15px;">'
            "No upcoming plans with linked songs found."
            "</td></tr></table>"
        )
    else:
        sections: list[str] = []
        for _, plan_rows in plan_groups:
            first = plan_rows[0]
            sections.append(
                '<table role="presentation" width="100%" cellpadding="0" cellspacing="0" '
                'style="margin:0 0 24px 0;background:#ffffff;border:1px solid #e5e7eb;'
                'border-radius:18px;">'
                '<tr><td style="padding:24px 24px 18px 24px;">'
                f'<div style="font-size:12px;color:#667085;font-weight:700;letter-spacing:0.06em;'
                'text-transform:uppercase;margin-bottom:8px;">'
                f"{escape(format_dt(first.sort_date))} | {escape(first.service_type_name)}</div>"
                f'<div style="font-size:24px;line-height:1.25;font-weight:700;color:#101828;'
                'margin-bottom:8px;">'
                f'<a href="{escape(plan_url(first.plan_id))}" '
                'style="color:#0969da;text-decoration:none;">'
                f"{escape(first.plan_title)}</a></div>"
                f'<div style="font-size:13px;color:#667085;">Plan link: '
                f'<a href="{escape(plan_url(first.plan_id))}" '
                'style="color:#0969da;text-decoration:none;">Open in Planning Center</a>'
                "</div></td></tr>"
                '<tr><td style="padding:0 24px 24px 24px;">'
                f"{render_plan_table_html(plan_rows)}"
                "</td></tr>"
                "</table>"
            )
        body = "".join(sections)

    return (
        '<html><body style="margin:0;padding:0;background:#f4f1ea;">'
        '<table role="presentation" width="100%" cellpadding="0" cellspacing="0" '
        'style="background:linear-gradient(180deg,#f4f1ea 0%,#ede7db 100%);padding:32px 16px;">'
        '<tr><td align="center">'
        '<table role="presentation" width="100%" cellpadding="0" cellspacing="0" '
        'style="max-width:760px;background:#fcfbf7;border:1px solid #e7dfd1;border-radius:24px;">'
        '<tr><td style="padding:32px 32px 12px 32px;">'
        '<div style="font-size:12px;font-weight:700;letter-spacing:0.08em;'
        'text-transform:uppercase;color:#8a6b2d;margin-bottom:10px;">New Song Magician</div>'
        '<h1 style="margin:0 0 10px 0;font-size:30px;line-height:1.15;color:#1f2937;">'
        "Upcoming song review digest</h1>"
        f'<p style="margin:0 0 20px 0;font-size:15px;line-height:1.6;color:#475467;">'
        "Planning Center folder: "
        f'<a href="{escape(folder_dashboard_url(folder_id))}" '
        'style="color:#0969da;text-decoration:none;font-weight:600;">'
        f"{escape(folder_id)}</a></p>"
        "</td></tr>"
        '<tr><td style="padding:0 32px 28px 32px;">'
        '<table role="presentation" width="100%" cellpadding="0" cellspacing="0"><tr>'
        '<td width="33.33%" style="padding-right:8px;">'
        '<table role="presentation" width="100%" cellpadding="0" cellspacing="0" '
        'style="background:#ffffff;border:1px solid #e7dfd1;border-radius:16px;"><tr><td '
        'style="padding:18px 18px 16px 18px;"><div style="font-size:12px;color:#667085;'
        'text-transform:uppercase;letter-spacing:0.05em;font-weight:700;">Plans</div>'
        '<div style="margin-top:8px;font-size:28px;font-weight:700;color:#101828;">'
        f"{len(plan_groups)}</div>"
        "</td></tr></table></td>"
        '<td width="33.33%" style="padding:0 4px;">'
        '<table role="presentation" width="100%" cellpadding="0" cellspacing="0" '
        'style="background:#ffffff;border:1px solid #e7dfd1;border-radius:16px;"><tr><td '
        'style="padding:18px 18px 16px 18px;"><div style="font-size:12px;color:#667085;'
        'text-transform:uppercase;letter-spacing:0.05em;font-weight:700;">Songs</div>'
        '<div style="margin-top:8px;font-size:28px;font-weight:700;color:#101828;">'
        f"{len(reports)}</div>"
        "</td></tr></table></td>"
        '<td width="33.33%" style="padding-left:8px;">'
        '<table role="presentation" width="100%" cellpadding="0" cellspacing="0" '
        'style="background:#fff7ed;border:1px solid #f5d7b3;border-radius:16px;"><tr><td '
        'style="padding:18px 18px 16px 18px;"><div style="font-size:12px;color:#9a3412;'
        'text-transform:uppercase;letter-spacing:0.05em;font-weight:700;">Needs Review</div>'
        '<div style="margin-top:8px;font-size:28px;font-weight:700;color:#9a3412;">'
        f"{review_count}</div>"
        "</td></tr></table></td>"
        "</tr></table></td></tr>"
        '<tr><td style="padding:0 32px 32px 32px;">'
        f"{body}"
        "</td></tr>"
        "</table></td></tr></table></body></html>"
    )


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
) -> tuple[list[dict[str, Any]], dict[str, dict[str, Any]], dict[str, dict[str, Any]]]:
    logger.debug("Fetching items for plan %s in service type %s", plan_id, service_type_id)
    payload = api.get_json(
        f"/services/v2/service_types/{service_type_id}/plans/{plan_id}/items",
        params={"include": "song,arrangement,key", "per_page": 100},
    )

    items = list(payload.get("data", []))
    songs_by_id: dict[str, dict[str, Any]] = {}
    arrangements_by_id: dict[str, dict[str, Any]] = {}

    for included in payload.get("included", []):
        if included.get("type") == "Song" and included.get("id"):
            songs_by_id[included["id"]] = included
        if included.get("type") == "Arrangement" and included.get("id"):
            arrangements_by_id[included["id"]] = included

    meta = payload.get("meta", {}) or {}
    total = meta.get("count", len(items))
    offset = len(items)

    while offset < total:
        next_payload = api.get_json(
            f"/services/v2/service_types/{service_type_id}/plans/{plan_id}/items",
            params={"include": "song,arrangement,key", "per_page": 100, "offset": offset},
        )
        next_items = next_payload.get("data", [])
        items.extend(next_items)

        for included in next_payload.get("included", []):
            if included.get("type") == "Song" and included.get("id"):
                songs_by_id[included["id"]] = included
            if included.get("type") == "Arrangement" and included.get("id"):
                arrangements_by_id[included["id"]] = included

        if not next_items:
            break
        offset += len(next_items)

    return items, songs_by_id, arrangements_by_id


def extract_real_song_items(items: list[dict[str, Any]]) -> list[tuple[str, dict[str, Any]]]:
    song_items: list[tuple[str, dict[str, Any]]] = []
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
        song_items.append((song_id, item))

    return song_items


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

        items, songs_by_id, arrangements_by_id = get_plan_items_with_songs(
            api, service_type_id, plan_id
        )
        cutoff = report_now - timedelta(days=review_window_years * 365)

        for song_id, item in extract_real_song_items(items):
            song_obj = songs_by_id.get(song_id, {"id": song_id, "attributes": {}})
            song_title = normalize_song_title(song_obj)
            if should_ignore_song(song_title):
                logger.debug("Skipping ignored song %r in plan %s", song_title, plan_id)
                continue

            arrangement_rel = item.get("relationships", {}).get("arrangement", {}).get("data")
            arrangement_id = arrangement_rel.get("id") if arrangement_rel else None
            arrangement_obj = (
                arrangements_by_id.get(arrangement_id, {"attributes": {}})
                if arrangement_id
                else {"attributes": {}}
            )
            arrangement_name = arrangement_obj.get("attributes", {}).get("name")
            key_name = item.get("attributes", {}).get("key_name")

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
                    arrangement_id=arrangement_id,
                    arrangement_name=arrangement_name,
                    key_name=key_name,
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
