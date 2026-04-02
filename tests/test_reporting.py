from __future__ import annotations

from urllib.parse import parse_qs, urlparse

import requests
import responses
from conftest import (
    FIXED_NOW,
    add_common_responses,
    arrangement,
    item,
    payload,
    plan,
    song,
    song_schedule,
)

from new_song_magician.client import PCOClient
from new_song_magician.reporting import (
    build_plan_song_report,
    render_full_report_html,
    render_full_report_markdown,
    render_plan_table,
)


@responses.activate
def test_build_report_uses_last_past_schedule_in_folder(api: PCOClient) -> None:
    add_common_responses(responses)
    responses.get(
        "https://api.planningcenteronline.com/services/v2/service_types/st-1/plans",
        json=payload(
            [
                plan("plan-1", "Plan One", "2026-04-10T10:00:00Z"),
                plan("plan-2", "Plan Two", "2026-04-20T10:00:00Z"),
            ]
        ),
    )
    responses.get(
        "https://api.planningcenteronline.com/services/v2/service_types/st-2/plans",
        json=payload([]),
    )
    responses.get(
        "https://api.planningcenteronline.com/services/v2/service_types/st-1/plans/plan-1/items",
        json=payload(
            [item("item-1", "song-1", arrangement_id="arr-1", key_name="D")],
            included=[
                song("song-1", "King of Glory"),
                arrangement("arr-1", "song-1", "The Worship Initiative"),
            ],
        ),
    )
    responses.get(
        "https://api.planningcenteronline.com/services/v2/service_types/st-1/plans/plan-2/items",
        json=payload([item("item-2", "song-1")], included=[song("song-1", "King of Glory")]),
    )

    captured_before_values: list[str] = []

    def song_schedule_callback(
        request: requests.PreparedRequest,
    ) -> tuple[int, dict[str, str], str]:
        query = parse_qs(urlparse(request.url).query)
        captured_before_values.append(query["before"][0])
        body = payload(
            [
                song_schedule(
                    plan_id="outside-folder-plan",
                    service_type_id="outside-folder-st",
                    plan_sort_date="2026-03-25T10:00:00Z",
                    plan_dates="Mar 25, 2026",
                    service_type_name="Special Event",
                    item_id="outside-item",
                ),
                song_schedule(
                    plan_id="prior-folder-plan",
                    service_type_id="st-1",
                    plan_sort_date="2025-05-01T10:00:00Z",
                    plan_dates="May 1, 2025",
                    service_type_name="Sunday AM",
                    item_id="prior-item",
                ),
            ]
        )
        return (200, {"Content-Type": "application/json"}, __import__("json").dumps(body))

    responses.add_callback(
        responses.GET,
        "https://api.planningcenteronline.com/services/v2/songs/song-1/song_schedules",
        callback=song_schedule_callback,
        content_type="application/json",
    )

    reports = build_plan_song_report(
        api,
        folder_id="folder-1",
        days_ahead=30,
        all_future=False,
        review_window_years=3,
    )

    assert len(reports) == 2
    assert [row.last_plan_id for row in reports] == ["prior-folder-plan", "prior-folder-plan"]
    assert [row.last_service_type_name for row in reports] == ["Sunday AM", "Sunday AM"]
    assert captured_before_values == [FIXED_NOW.isoformat()]


@responses.activate
def test_build_report_flags_brand_new_song_in_folder(api: PCOClient) -> None:
    add_common_responses(responses)
    responses.get(
        "https://api.planningcenteronline.com/services/v2/service_types/st-1/plans",
        json=payload([plan("plan-1", "Plan One", "2026-04-10T10:00:00Z")]),
    )
    responses.get(
        "https://api.planningcenteronline.com/services/v2/service_types/st-2/plans",
        json=payload([]),
    )
    responses.get(
        "https://api.planningcenteronline.com/services/v2/service_types/st-1/plans/plan-1/items",
        json=payload([item("item-1", "song-new")], included=[song("song-new", "Brand New Song")]),
    )
    responses.get(
        "https://api.planningcenteronline.com/services/v2/songs/song-new/song_schedules",
        json=payload([]),
    )

    reports = build_plan_song_report(
        api,
        folder_id="folder-1",
        days_ahead=30,
        all_future=False,
        review_window_years=3,
    )

    assert len(reports) == 1
    row = reports[0]
    assert row.song_title == "Brand New Song"
    assert row.needs_review is True
    assert row.last_played_at is None
    assert "never scheduled in folder" in render_plan_table(reports)


@responses.activate
def test_build_report_skips_current_plan_if_api_returns_it(api: PCOClient) -> None:
    add_common_responses(responses)
    responses.get(
        "https://api.planningcenteronline.com/services/v2/service_types/st-1/plans",
        json=payload([plan("plan-1", "Plan One", "2026-04-10T10:00:00Z")]),
    )
    responses.get(
        "https://api.planningcenteronline.com/services/v2/service_types/st-2/plans",
        json=payload([]),
    )
    responses.get(
        "https://api.planningcenteronline.com/services/v2/service_types/st-1/plans/plan-1/items",
        json=payload([item("item-1", "song-1")], included=[song("song-1", "King of Glory")]),
    )
    responses.get(
        "https://api.planningcenteronline.com/services/v2/songs/song-1/song_schedules",
        json=payload(
            [
                song_schedule(
                    plan_id="plan-1",
                    service_type_id="st-1",
                    plan_sort_date="2026-04-10T10:00:00Z",
                    plan_dates="Apr 10, 2026",
                    service_type_name="Sunday AM",
                    item_id="item-1",
                ),
                song_schedule(
                    plan_id="older-plan",
                    service_type_id="st-1",
                    plan_sort_date="2025-04-10T10:00:00Z",
                    plan_dates="Apr 10, 2025",
                    service_type_name="Sunday AM",
                    item_id="older-item",
                ),
            ]
        ),
    )

    reports = build_plan_song_report(
        api,
        folder_id="folder-1",
        days_ahead=30,
        all_future=False,
        review_window_years=3,
    )

    assert len(reports) == 1
    assert reports[0].last_plan_id == "older-plan"
    assert reports[0].last_item_id == "older-item"


@responses.activate
def test_build_report_ignores_doxology(api: PCOClient) -> None:
    add_common_responses(responses)
    responses.get(
        "https://api.planningcenteronline.com/services/v2/service_types/st-1/plans",
        json=payload([plan("plan-1", "Plan One", "2026-04-10T10:00:00Z")]),
    )
    responses.get(
        "https://api.planningcenteronline.com/services/v2/service_types/st-2/plans",
        json=payload([]),
    )
    responses.get(
        "https://api.planningcenteronline.com/services/v2/service_types/st-1/plans/plan-1/items",
        json=payload([item("item-1", "song-dox")], included=[song("song-dox", "Doxology")]),
    )

    reports = build_plan_song_report(
        api,
        folder_id="folder-1",
        days_ahead=30,
        all_future=False,
        review_window_years=3,
    )

    assert reports == []


@responses.activate
def test_rendered_table_shows_review_and_ok_rows(api: PCOClient) -> None:
    add_common_responses(responses)
    responses.get(
        "https://api.planningcenteronline.com/services/v2/service_types/st-1/plans",
        json=payload(
            [
                plan("plan-1", "Plan One", "2026-04-10T10:00:00Z"),
                plan("plan-2", "Plan Two", "2026-04-20T10:00:00Z"),
            ]
        ),
    )
    responses.get(
        "https://api.planningcenteronline.com/services/v2/service_types/st-2/plans",
        json=payload([]),
    )
    responses.get(
        "https://api.planningcenteronline.com/services/v2/service_types/st-1/plans/plan-1/items",
        json=payload([item("item-1", "song-old")], included=[song("song-old", "Ancient Song")]),
    )
    responses.get(
        "https://api.planningcenteronline.com/services/v2/service_types/st-1/plans/plan-2/items",
        json=payload([item("item-2", "song-new")], included=[song("song-new", "Fresh Song")]),
    )
    responses.get(
        "https://api.planningcenteronline.com/services/v2/songs/song-old/song_schedules",
        json=payload(
            [
                song_schedule(
                    plan_id="recent-plan",
                    service_type_id="st-1",
                    plan_sort_date="2025-12-20T10:00:00Z",
                    plan_dates="Dec 20, 2025",
                    service_type_name="Sunday AM",
                    item_id="recent-item",
                )
            ]
        ),
    )
    responses.get(
        "https://api.planningcenteronline.com/services/v2/songs/song-new/song_schedules",
        json=payload([]),
    )

    reports = build_plan_song_report(
        api,
        folder_id="folder-1",
        days_ahead=30,
        all_future=False,
        review_window_years=3,
    )

    assert len(reports) == 2
    rendered = render_plan_table(reports)
    header_line = rendered.splitlines()[0]
    assert "Status" in header_line
    assert "Song Link" in header_line
    assert "Last Scheduled" in header_line
    assert "Last Plan Link" in header_line
    assert "OK" in rendered
    assert "REVIEW" in rendered
    assert "never scheduled in folder" in rendered
    assert "https://services.planningcenteronline.com/songs/song-old" in rendered
    assert "https://services.planningcenteronline.com/plans/recent-plan" in rendered


@responses.activate
def test_build_report_handles_multi_page_plan_items(api: PCOClient) -> None:
    add_common_responses(responses)
    responses.get(
        "https://api.planningcenteronline.com/services/v2/service_types/st-1/plans",
        json=payload([plan("plan-1", "Plan One", "2026-04-10T10:00:00Z")]),
    )
    responses.get(
        "https://api.planningcenteronline.com/services/v2/service_types/st-2/plans",
        json=payload([]),
    )
    responses.get(
        "https://api.planningcenteronline.com/services/v2/service_types/st-1/plans/plan-1/items",
        json=payload(
            [item("item-1", "song-1")],
            included=[song("song-1", "King of Glory")],
            count=2,
        ),
    )
    responses.get(
        "https://api.planningcenteronline.com/services/v2/service_types/st-1/plans/plan-1/items"
        "?include=song%2Carrangement%2Ckey&offset=1&per_page=100",
        json=payload(
            [item("item-2", "song-2")],
            included=[song("song-2", "Cornerstone")],
            count=2,
        ),
    )
    responses.get(
        "https://api.planningcenteronline.com/services/v2/songs/song-1/song_schedules",
        json=payload([]),
    )
    responses.get(
        "https://api.planningcenteronline.com/services/v2/songs/song-2/song_schedules",
        json=payload([]),
    )

    reports = build_plan_song_report(
        api,
        folder_id="folder-1",
        days_ahead=30,
        all_future=False,
        review_window_years=3,
    )

    assert len(reports) == 2
    assert [row.song_title for row in reports] == ["King of Glory", "Cornerstone"]


@responses.activate
def test_full_report_rendering_includes_folder_plan_and_song_links(api: PCOClient) -> None:
    add_common_responses(responses, folder_id="342915")
    responses.get(
        "https://api.planningcenteronline.com/services/v2/service_types/st-1/plans",
        json=payload([plan("plan-1", "Plan One", "2026-04-10T10:00:00Z")]),
    )
    responses.get(
        "https://api.planningcenteronline.com/services/v2/service_types/st-2/plans",
        json=payload([]),
    )
    responses.get(
        "https://api.planningcenteronline.com/services/v2/service_types/st-1/plans/plan-1/items",
        json=payload(
            [item("item-1", "song-1", arrangement_id="arr-1", key_name="D")],
            included=[
                song("song-1", "King of Glory"),
                arrangement("arr-1", "song-1", "The Worship Initiative"),
            ],
        ),
    )
    responses.get(
        "https://api.planningcenteronline.com/services/v2/songs/song-1/song_schedules",
        json=payload([]),
    )

    reports = build_plan_song_report(
        api,
        folder_id="342915",
        days_ahead=30,
        all_future=False,
        review_window_years=3,
    )

    markdown = render_full_report_markdown(reports)
    html = render_full_report_html(reports, folder_id="342915")

    assert "https://services.planningcenteronline.com/plans/plan-1" in markdown
    assert "https://services.planningcenteronline.com/songs/song-1" in markdown
    assert "The Worship Initiative" in html
    assert "Scheduled key: D" in html
    assert (
        'href="https://services.planningcenteronline.com/songs/song-1/arrangements/arr-1"' in html
    )
    assert "Upcoming song review digest" in html
    assert "Needs Review" in html
    assert "Song ID: song-1" in html
    assert 'href="https://services.planningcenteronline.com/dashboard/342915"' in html
    assert 'href="https://services.planningcenteronline.com/plans/plan-1"' in html
    assert 'href="https://services.planningcenteronline.com/songs/song-1"' in html
