from __future__ import annotations

import responses
from click.testing import CliRunner
from conftest import add_common_responses, item, payload, plan, song, song_schedule

from new_song_magician.cli import BASE_URL, cli


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
        json=payload([item("item-1", "song-1")], included=[song("song-1", "King of Glory")]),
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
    assert '"song_title": "King of Glory"' in result.output
    assert '"last_plan_id": "older-plan"' in result.output
    assert '"needs_review": false' in result.output
