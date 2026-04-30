from __future__ import annotations

from urllib.parse import parse_qs, urlparse

import requests
import responses
from conftest import (
    FIXED_NOW,
    add_common_responses,
    arrangement,
    attachment,
    item,
    payload,
    plan,
    song,
    song_schedule,
)

from new_song_magician.client import PCOClient
from new_song_magician.reporting import (
    build_plan_song_report,
    call_to_worship_key_from_title,
    normalize_key_name,
    normalize_musical_key_name,
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
            [
                item(
                    "item-ctw-1",
                    None,
                    item_type="item",
                    title="Call to worship; Encouragement; Time for Reflection [Key of C]",
                ),
                item("item-1", "song-1", arrangement_id="arr-1", key_name="C"),
            ],
            included=[
                song("song-1", "King of Glory"),
                arrangement("arr-1", "song-1", "The Worship Initiative"),
            ],
        ),
    )
    responses.get(
        "https://api.planningcenteronline.com/services/v2/service_types/st-1/plans/plan-2/items",
        json=payload(
            [
                item(
                    "item-ctw-2",
                    None,
                    item_type="item",
                    title="Call to worship; Encouragement; Time for Reflection [Key of C]",
                ),
                item("item-2", "song-1", key_name="C"),
            ],
            included=[song("song-1", "King of Glory")],
        ),
    )
    responses.get(
        "https://api.planningcenteronline.com/services/v2/service_types/st-1/plans/plan-1/items/item-ctw-1/attachments",
        json=payload(
            [attachment("att-1", display_name="Pad chart", url="https://files.example/ctw-1.pdf")]
        ),
    )
    responses.get(
        "https://api.planningcenteronline.com/services/v2/service_types/st-1/plans/plan-2/items/item-ctw-2/attachments",
        json=payload(
            [attachment("att-2", display_name="Pad chart", url="https://files.example/ctw-2.pdf")]
        ),
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
                    arrangement_name="Acoustic",
                    key_name="D",
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
        key_history_count=3,
    )

    song_rows = [row for row in reports if row.report_type == "song"]
    call_rows = [row for row in reports if row.report_type == "call_to_worship"]
    assert len(song_rows) == 2
    assert len(call_rows) == 2
    assert [row.last_plan_id for row in song_rows] == ["prior-folder-plan", "prior-folder-plan"]
    assert [row.last_service_type_name for row in song_rows] == ["Sunday AM", "Sunday AM"]
    assert [row.recent_keys for row in song_rows] == [("D",), ("D",)]
    assert [row.key_comparison for row in song_rows] == ["Different from recent keys"] * 2
    assert all(row.item_key_is_set is True for row in call_rows)
    assert captured_before_values == [FIXED_NOW.isoformat()]


def test_normalize_key_name_and_recent_key_formatting() -> None:
    assert normalize_key_name("Bb: Original") == "Bb"
    assert normalize_key_name("A: 1/2 Step Lower Than Original") == "A"


def test_normalize_musical_key_name_accepts_real_keys_only() -> None:
    assert normalize_musical_key_name("c") == "C"
    assert normalize_musical_key_name(" f#m ") == "F#m"
    assert normalize_musical_key_name("Bb") == "Bb"
    assert normalize_musical_key_name("Pad") is None
    assert normalize_musical_key_name("Strong") is None


def test_call_to_worship_key_from_title_rejects_non_musical_values() -> None:
    assert call_to_worship_key_from_title("Call to worship [Key of D]") == (True, "D")
    assert call_to_worship_key_from_title("Call to worship [Key of F#m]") == (True, "F#m")
    assert call_to_worship_key_from_title("Call to worship [Key of Pad]") == (False, None)
    assert call_to_worship_key_from_title("Call to worship [Key of Strong]") == (False, None)


@responses.activate
def test_build_report_skips_plan_with_no_songs_even_if_call_to_worship_exists(
    api: PCOClient,
) -> None:
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
            [
                item(
                    "item-ctw-1",
                    None,
                    item_type="item",
                    title="Call to worship; Encouragement; Time for Reflection [Key of C]",
                )
            ]
        ),
    )
    responses.get(
        "https://api.planningcenteronline.com/services/v2/service_types/st-1/plans/plan-1/items/item-ctw-1/attachments",
        json=payload(
            [attachment("att-1", display_name="Pad chart", url="https://files.example/ctw-1.pdf")]
        ),
    )

    reports = build_plan_song_report(
        api,
        folder_id="folder-1",
        days_ahead=30,
        all_future=False,
        review_window_years=3,
        key_history_count=3,
    )

    assert reports == []


@responses.activate
def test_build_report_can_disable_call_to_worship_rows(api: PCOClient) -> None:
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
            [
                item(
                    "item-ctw-1",
                    None,
                    item_type="item",
                    title="Call to worship; Encouragement; Time for Reflection [Key of Pad]",
                ),
                item("item-1", "song-1"),
            ],
            included=[song("song-1", "King of Glory")],
        ),
    )
    responses.get(
        "https://api.planningcenteronline.com/services/v2/songs/song-1/song_schedules",
        json=payload([]),
    )

    reports = build_plan_song_report(
        api,
        folder_id="folder-1",
        days_ahead=30,
        all_future=False,
        review_window_years=3,
        key_history_count=3,
        include_call_to_worship=False,
    )

    assert len(reports) == 1
    assert reports[0].report_type == "song"


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
        json=payload(
            [
                item(
                    "item-ctw-1",
                    None,
                    item_type="item",
                    title="Call to worship; Encouragement; Time for Reflection [Key of C]",
                ),
                item("item-1", "song-new"),
            ],
            included=[song("song-new", "Brand New Song")],
        ),
    )
    responses.get(
        "https://api.planningcenteronline.com/services/v2/service_types/st-1/plans/plan-1/items/item-ctw-1/attachments",
        json=payload(
            [attachment("att-1", display_name="Pad chart", url="https://files.example/ctw-1.pdf")]
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
        key_history_count=3,
    )

    song_rows = [row for row in reports if row.report_type == "song"]
    assert len(song_rows) == 1
    row = song_rows[0]
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
        json=payload(
            [
                item(
                    "item-ctw-1",
                    None,
                    item_type="item",
                    title="Call to worship; Encouragement; Time for Reflection [Key of C]",
                ),
                item("item-1", "song-1"),
            ],
            included=[song("song-1", "King of Glory")],
        ),
    )
    responses.get(
        "https://api.planningcenteronline.com/services/v2/service_types/st-1/plans/plan-1/items/item-ctw-1/attachments",
        json=payload(
            [attachment("att-1", display_name="Pad chart", url="https://files.example/ctw-1.pdf")]
        ),
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
        key_history_count=3,
    )

    song_rows = [row for row in reports if row.report_type == "song"]
    assert len(song_rows) == 1
    assert song_rows[0].last_plan_id == "older-plan"
    assert song_rows[0].last_item_id == "older-item"


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
        json=payload(
            [
                item(
                    "item-ctw-1",
                    None,
                    item_type="item",
                    title="Call to worship; Encouragement; Time for Reflection [Key of C]",
                ),
                item("item-1", "song-dox"),
            ],
            included=[song("song-dox", "Doxology")],
        ),
    )
    responses.get(
        "https://api.planningcenteronline.com/services/v2/service_types/st-1/plans/plan-1/items/item-ctw-1/attachments",
        json=payload(
            [attachment("att-1", display_name="Pad chart", url="https://files.example/ctw-1.pdf")]
        ),
    )

    reports = build_plan_song_report(
        api,
        folder_id="folder-1",
        days_ahead=30,
        all_future=False,
        review_window_years=3,
        key_history_count=3,
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
        json=payload(
            [
                item(
                    "item-ctw-1",
                    None,
                    item_type="item",
                    title="Call to worship; Encouragement; Time for Reflection [Key of Pad]",
                ),
                item("item-1", "song-old"),
            ],
            included=[song("song-old", "Ancient Song")],
        ),
    )
    responses.get(
        "https://api.planningcenteronline.com/services/v2/service_types/st-1/plans/plan-2/items",
        json=payload(
            [
                item(
                    "item-ctw-2",
                    None,
                    item_type="item",
                    title="Call to worship; Encouragement; Time for Reflection [Key of C]",
                ),
                item("item-2", "song-new"),
            ],
            included=[song("song-new", "Fresh Song")],
        ),
    )
    responses.get(
        "https://api.planningcenteronline.com/services/v2/service_types/st-1/plans/plan-1/items/item-ctw-1/attachments",
        json=payload([]),
    )
    responses.get(
        "https://api.planningcenteronline.com/services/v2/service_types/st-1/plans/plan-2/items/item-ctw-2/attachments",
        json=payload(
            [
                attachment(
                    "att-2", display_name="Reflection Pad", url="https://files.example/ctw-2.pdf"
                )
            ]
        ),
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
        key_history_count=3,
    )

    assert len(reports) == 4
    rendered = render_plan_table(reports)
    header_line = rendered.splitlines()[0]
    assert "Status" in header_line
    assert "Entry Link" in header_line
    assert "Last Scheduled" in header_line
    assert "Last Plan Link" in header_line
    assert "OK" in rendered
    assert "REVIEW" in rendered
    assert "never scheduled in folder" in rendered
    assert "Missing key in title; Missing attachment" in rendered
    assert "Reflection Pad: https://files.example/ctw-2.pdf" in rendered
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
            [
                item(
                    "item-ctw-1",
                    None,
                    item_type="item",
                    title="Call to worship; Encouragement; Time for Reflection [Key of C]",
                ),
                item("item-1", "song-1"),
            ],
            included=[song("song-1", "King of Glory")],
            count=3,
        ),
    )
    responses.get(
        "https://api.planningcenteronline.com/services/v2/service_types/st-1/plans/plan-1/items"
        "?include=song%2Carrangement%2Ckey&offset=2&per_page=100",
        json=payload(
            [item("item-2", "song-2")],
            included=[song("song-2", "Cornerstone")],
            count=3,
        ),
    )
    responses.get(
        "https://api.planningcenteronline.com/services/v2/service_types/st-1/plans/plan-1/items/item-ctw-1/attachments",
        json=payload(
            [attachment("att-1", display_name="Pad chart", url="https://files.example/ctw-1.pdf")]
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
        key_history_count=3,
    )

    song_rows = [row for row in reports if row.report_type == "song"]
    assert len(song_rows) == 2
    assert [row.song_title for row in song_rows] == ["King of Glory", "Cornerstone"]


@responses.activate
def test_build_report_can_disable_key_history_comparison(api: PCOClient) -> None:
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
            [
                item(
                    "item-ctw-1",
                    None,
                    item_type="item",
                    title="Call to worship; Encouragement; Time for Reflection [Key of C]",
                ),
                item("item-1", "song-1", key_name="C"),
            ],
            included=[song("song-1", "King")],
        ),
    )
    responses.get(
        "https://api.planningcenteronline.com/services/v2/service_types/st-1/plans/plan-1/items/item-ctw-1/attachments",
        json=payload(
            [attachment("att-1", display_name="Pad chart", url="https://files.example/ctw-1.pdf")]
        ),
    )
    responses.get(
        "https://api.planningcenteronline.com/services/v2/songs/song-1/song_schedules",
        json=payload(
            [
                song_schedule(
                    plan_id="older-plan",
                    service_type_id="st-1",
                    plan_sort_date="2025-04-10T10:00:00Z",
                    plan_dates="Apr 10, 2025",
                    service_type_name="Sunday AM",
                    item_id="older-item",
                    key_name="D",
                )
            ]
        ),
    )

    reports = build_plan_song_report(
        api,
        folder_id="folder-1",
        days_ahead=30,
        all_future=False,
        review_window_years=3,
        key_history_count=0,
    )

    song_row = next(row for row in reports if row.report_type == "song")
    assert song_row.recent_keys == ()
    assert song_row.key_comparison is None


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
            [
                item(
                    "item-ctw-1",
                    None,
                    item_type="item",
                    title="Call to worship; Encouragement; Time for Reflection [Key of C]",
                ),
                item("item-1", "song-1", arrangement_id="arr-1", key_name="D"),
            ],
            included=[
                song("song-1", "King of Glory"),
                arrangement("arr-1", "song-1", "The Worship Initiative"),
            ],
        ),
    )
    responses.get(
        "https://api.planningcenteronline.com/services/v2/service_types/st-1/plans/plan-1/items/item-ctw-1/attachments",
        json=payload(
            [
                attachment(
                    "att-1", display_name="Reflection Pad", url="https://files.example/ctw-1.pdf"
                )
            ]
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
        key_history_count=3,
    )

    markdown = render_full_report_markdown(reports)
    html = render_full_report_html(reports, folder_id="342915")

    assert "https://services.planningcenteronline.com/plans/plan-1" in markdown
    assert "https://services.planningcenteronline.com/songs/song-1" in markdown
    assert "Reflection Pad: https://files.example/ctw-1.pdf" in markdown
    assert "The Worship Initiative" in html
    assert "Scheduled key: D" in html
    assert "Call to worship; Encouragement; Time for Reflection [Key of C]" in html
    assert "Reflection Pad" in html
    assert (
        'href="https://services.planningcenteronline.com/songs/song-1/arrangements/arr-1"' in html
    )
    assert "Upcoming song review digest" in html
    assert "Needs Review" in html
    assert "Song ID: song-1" in html
    assert 'href="https://services.planningcenteronline.com/dashboard/342915"' in html
    assert 'href="https://services.planningcenteronline.com/plans/plan-1"' in html
    assert 'href="https://services.planningcenteronline.com/songs/song-1"' in html


@responses.activate
def test_build_report_adds_call_to_worship_review_row_when_key_or_attachment_missing(
    api: PCOClient,
) -> None:
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
            [
                item(
                    "item-ctw-1",
                    None,
                    item_type="item",
                    title="Call to worship; Encouragement; Time for Reflection [Key of Pad]",
                )
            ]
        ),
    )
    responses.get(
        "https://api.planningcenteronline.com/services/v2/service_types/st-1/plans/plan-1/items/item-ctw-1/attachments",
        json=payload([]),
    )

    reports = build_plan_song_report(
        api,
        folder_id="folder-1",
        days_ahead=30,
        all_future=False,
        review_window_years=3,
        key_history_count=3,
    )

    assert reports == []
