from __future__ import annotations

import sys

import responses
from click.testing import CliRunner
from conftest import (
    add_common_responses,
    arrangement,
    attachment,
    item,
    payload,
    plan,
    song,
    song_schedule,
)

from new_song_magician.cli import BASE_URL, cli

cli_module = sys.modules["new_song_magician.cli"]


@responses.activate
def test_lookup_folder_cli_outputs_matching_folder(runner: CliRunner) -> None:
    responses.get(
        f"{BASE_URL}/services/v2/folders",
        json=payload(
            [
                {"id": "folder-1", "type": "Folder", "attributes": {"name": "Sunday Worship"}},
                {"id": "folder-2", "type": "Folder", "attributes": {"name": "Students"}},
            ]
        ),
    )

    result = runner.invoke(
        cli,
        [
            "--app-id",
            "app-id",
            "--secret",
            "secret",
            "lookup-folder",
            "Sunday Worship",
        ],
    )

    assert result.exit_code == 0
    assert "folder-1\tSunday Worship" in result.output


@responses.activate
def test_review_folder_cli_json_output(runner: CliRunner) -> None:
    add_common_responses(responses)
    responses.get(
        f"{BASE_URL}/services/v2/service_types/st-1/plans",
        json=payload([plan("plan-1", "Plan One", "2026-04-10T10:00:00Z")]),
    )
    responses.get(f"{BASE_URL}/services/v2/service_types/st-2/plans", json=payload([]))
    responses.get(
        f"{BASE_URL}/services/v2/service_types/st-1/plans/plan-1/items",
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
        f"{BASE_URL}/services/v2/service_types/st-1/plans/plan-1/items/item-ctw-1/attachments",
        json=payload(
            [
                attachment(
                    "att-1", display_name="Reflection Pad", url="https://files.example/ctw-1.pdf"
                )
            ]
        ),
    )
    responses.get(
        f"{BASE_URL}/services/v2/songs/song-1/song_schedules",
        json=payload(
            [
                song_schedule(
                    plan_id="older-plan",
                    service_type_id="st-1",
                    plan_sort_date="2025-04-10T10:00:00Z",
                    plan_dates="Apr 10, 2025",
                    service_type_name="Sunday AM",
                    item_id="older-item",
                    arrangement_name="The Worship Initiative",
                    key_name="C",
                )
            ]
        ),
    )

    result = runner.invoke(
        cli,
        [
            "--app-id",
            "app-id",
            "--secret",
            "secret",
            "review-folder",
            "folder-1",
            "--json-output",
        ],
    )

    assert result.exit_code == 0
    assert '"report_type": "call_to_worship"' in result.output
    assert '"item_key_is_set": true' in result.output
    assert '"attachment_links": [' in result.output
    assert '"song_title": "King of Glory"' in result.output
    assert '"arrangement_name": "The Worship Initiative"' in result.output
    assert '"key_name": "D"' in result.output
    assert '"recent_keys": [' in result.output
    assert '"key_comparison": "Different from recent keys"' in result.output
    assert (
        '"arrangement_url": "https://services.planningcenteronline.com/songs/song-1/arrangements/arr-1"'
        in result.output
    )
    assert '"last_plan_id": "older-plan"' in result.output
    assert '"plan_url": "https://services.planningcenteronline.com/plans/plan-1"' in result.output
    assert '"song_url": "https://services.planningcenteronline.com/songs/song-1"' in result.output
    assert (
        '"folder_url": "https://services.planningcenteronline.com/dashboard/folder-1"'
        in result.output
    )
    assert '"needs_review": false' in result.output


@responses.activate
def test_review_folder_cli_sends_email_to_flagged_recipients(
    runner: CliRunner,
    monkeypatch,
) -> None:
    add_common_responses(responses)
    responses.get(
        f"{BASE_URL}/services/v2/service_types/st-1/plans",
        json=payload([plan("plan-1", "Plan One", "2026-04-10T10:00:00Z")]),
    )
    responses.get(f"{BASE_URL}/services/v2/service_types/st-2/plans", json=payload([]))
    responses.get(
        f"{BASE_URL}/services/v2/service_types/st-1/plans/plan-1/items",
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
        f"{BASE_URL}/services/v2/service_types/st-1/plans/plan-1/items/item-ctw-1/attachments",
        json=payload(
            [
                attachment(
                    "att-1", display_name="Reflection Pad", url="https://files.example/ctw-1.pdf"
                )
            ]
        ),
    )
    responses.get(
        f"{BASE_URL}/services/v2/songs/song-1/song_schedules",
        json=payload([]),
    )

    captured: dict[str, object] = {}

    def fake_send_report_email(
        config,
        recipients: tuple[str, ...],
        *,
        subject: str,
        text_body: str,
        html_body: str,
    ) -> None:
        captured["config"] = config
        captured["recipients"] = recipients
        captured["subject"] = subject
        captured["text_body"] = text_body
        captured["html_body"] = html_body

    monkeypatch.setattr(cli_module, "send_report_email", fake_send_report_email)

    result = runner.invoke(
        cli,
        [
            "--app-id",
            "app-id",
            "--secret",
            "secret",
            "review-folder",
            "folder-1",
            "--email",
            "a@example.com",
            "--email",
            "b@example.com",
        ],
    )

    assert result.exit_code == 0
    assert captured["recipients"] == ("a@example.com", "b@example.com")
    assert captured["subject"] == "New Song Magician report for folder folder-1"
    assert "King of Glory" in str(captured["text_body"])
    assert "<table" in str(captured["html_body"])
    assert "https://services.planningcenteronline.com/plans/plan-1" in str(captured["text_body"])
    assert "https://services.planningcenteronline.com/songs/song-1" in str(captured["text_body"])
    assert "Reflection Pad" in str(captured["text_body"])
    assert "The Worship Initiative" in str(captured["html_body"])
    assert "Call to worship; Encouragement; Time for Reflection [Key of C]" in str(
        captured["html_body"]
    )
    assert "Scheduled key: D" in str(captured["html_body"])
    assert "King of Glory" in result.output


@responses.activate
def test_review_folder_cli_reads_email_recipients_from_env_var(
    runner: CliRunner, monkeypatch
) -> None:
    add_common_responses(responses)
    responses.get(
        f"{BASE_URL}/services/v2/service_types/st-1/plans",
        json=payload([plan("plan-1", "Plan One", "2026-04-10T10:00:00Z")]),
    )
    responses.get(f"{BASE_URL}/services/v2/service_types/st-2/plans", json=payload([]))
    responses.get(
        f"{BASE_URL}/services/v2/service_types/st-1/plans/plan-1/items",
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
        f"{BASE_URL}/services/v2/service_types/st-1/plans/plan-1/items/item-ctw-1/attachments",
        json=payload(
            [
                attachment(
                    "att-1", display_name="Reflection Pad", url="https://files.example/ctw-1.pdf"
                )
            ]
        ),
    )
    responses.get(
        f"{BASE_URL}/services/v2/songs/song-1/song_schedules",
        json=payload([]),
    )

    captured: dict[str, object] = {}

    def fake_send_report_email(
        config,
        recipients: tuple[str, ...],
        *,
        subject: str,
        text_body: str,
        html_body: str,
    ) -> None:
        captured["recipients"] = recipients

    monkeypatch.setattr(cli_module, "send_report_email", fake_send_report_email)

    result = runner.invoke(
        cli,
        [
            "--app-id",
            "app-id",
            "--secret",
            "secret",
            "review-folder",
            "folder-1",
        ],
        env={"PCO_REVIEW_FOLDER_EMAILS": "a@example.com b@example.com"},
    )

    assert result.exit_code == 0
    assert captured["recipients"] == ("a@example.com", "b@example.com")


@responses.activate
def test_review_folder_cli_no_print_suppresses_stdout_when_emailing(
    runner: CliRunner,
    monkeypatch,
) -> None:
    add_common_responses(responses)
    responses.get(
        f"{BASE_URL}/services/v2/service_types/st-1/plans",
        json=payload([plan("plan-1", "Plan One", "2026-04-10T10:00:00Z")]),
    )
    responses.get(f"{BASE_URL}/services/v2/service_types/st-2/plans", json=payload([]))
    responses.get(
        f"{BASE_URL}/services/v2/service_types/st-1/plans/plan-1/items",
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
        f"{BASE_URL}/services/v2/service_types/st-1/plans/plan-1/items/item-ctw-1/attachments",
        json=payload(
            [
                attachment(
                    "att-1", display_name="Reflection Pad", url="https://files.example/ctw-1.pdf"
                )
            ]
        ),
    )
    responses.get(
        f"{BASE_URL}/services/v2/songs/song-1/song_schedules",
        json=payload([]),
    )

    monkeypatch.setattr(cli_module, "send_report_email", lambda *args, **kwargs: None)

    result = runner.invoke(
        cli,
        [
            "--app-id",
            "app-id",
            "--secret",
            "secret",
            "review-folder",
            "folder-1",
            "--email",
            "a@example.com",
            "--no-print",
        ],
    )

    assert result.exit_code == 0
    assert result.output == ""


@responses.activate
def test_review_folder_cli_can_disable_call_to_worship_with_env_var(runner: CliRunner) -> None:
    add_common_responses(responses)
    responses.get(
        f"{BASE_URL}/services/v2/service_types/st-1/plans",
        json=payload([plan("plan-1", "Plan One", "2026-04-10T10:00:00Z")]),
    )
    responses.get(f"{BASE_URL}/services/v2/service_types/st-2/plans", json=payload([]))
    responses.get(
        f"{BASE_URL}/services/v2/service_types/st-1/plans/plan-1/items",
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
        f"{BASE_URL}/services/v2/songs/song-1/song_schedules",
        json=payload([]),
    )

    result = runner.invoke(
        cli,
        [
            "--app-id",
            "app-id",
            "--secret",
            "secret",
            "review-folder",
            "folder-1",
            "--json-output",
        ],
        env={"PCO_REVIEW_FOLDER_CALL_TO_WORSHIP": "false"},
    )

    assert result.exit_code == 0
    assert '"report_type": "song"' in result.output
    assert '"report_type": "call_to_worship"' not in result.output
