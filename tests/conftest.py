from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import httpx
import pytest
import requests
import responses
from click.testing import CliRunner

import new_song_magician.reporting as reporting
from new_song_magician.cli import BASE_URL
from new_song_magician.client import PCOClient
from new_song_magician.models import Config

FIXED_NOW = datetime(2026, 4, 1, 12, 0, tzinfo=UTC)


class FixedDateTime(datetime):
    @classmethod
    def now(cls, tz: UTC | None = None) -> datetime:
        if tz is None:
            return FIXED_NOW.replace(tzinfo=None)
        return FIXED_NOW.astimezone(tz)


@pytest.fixture(autouse=True)
def freeze_time(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(reporting, "datetime", FixedDateTime)


@pytest.fixture(autouse=True)
def route_httpx_through_requests(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_get(
        client: httpx.Client,
        path: str,
        params: dict[str, Any] | None = None,
    ) -> requests.Response:
        request = client.build_request("GET", path, params=params)
        response = requests.get(str(request.url), headers=dict(request.headers), timeout=30.0)
        response.request = requests.Request("GET", str(request.url)).prepare()
        return response

    monkeypatch.setattr(httpx.Client, "get", fake_get)


@pytest.fixture
def api() -> PCOClient:
    client = PCOClient(
        Config(
            app_id="app-id",
            secret="secret",
            token=None,
            base_url=BASE_URL,
            timeout=30.0,
            gmail_credentials_file="gmail-oauth-client-secret.json",
            gmail_token_file=".gmail-token.json",
            gmail_from=None,
        )
    )
    try:
        yield client
    finally:
        client.close()


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


def payload(
    data: list[dict[str, Any]],
    *,
    included: list[dict[str, Any]] | None = None,
    count: int | None = None,
) -> dict[str, Any]:
    body: dict[str, Any] = {"data": data, "meta": {"count": len(data) if count is None else count}}
    if included is not None:
        body["included"] = included
    return body


def service_type(id_: str, name: str) -> dict[str, Any]:
    return {"id": id_, "type": "ServiceType", "attributes": {"name": name}}


def plan(id_: str, title: str, sort_date: str) -> dict[str, Any]:
    return {
        "id": id_,
        "type": "Plan",
        "attributes": {"title": title, "sort_date": sort_date},
    }


def song(song_id: str, title: str) -> dict[str, Any]:
    return {"id": song_id, "type": "Song", "attributes": {"title": title}}


def arrangement(arrangement_id: str, song_id: str, name: str) -> dict[str, Any]:
    return {
        "id": arrangement_id,
        "type": "Arrangement",
        "attributes": {"name": name},
        "relationships": {"song": {"data": {"id": song_id, "type": "Song"}}},
    }


def item(
    item_id: str,
    song_id: str,
    *,
    arrangement_id: str | None = None,
    key_name: str | None = None,
) -> dict[str, Any]:
    return {
        "id": item_id,
        "type": "Item",
        "attributes": {"item_type": "song", "key_name": key_name},
        "relationships": {
            "song": {"data": {"id": song_id, "type": "Song"}},
            "arrangement": (
                {"data": {"id": arrangement_id, "type": "Arrangement"}}
                if arrangement_id
                else {"data": None}
            ),
        },
    }


def song_schedule(
    *,
    plan_id: str,
    service_type_id: str,
    plan_sort_date: str,
    plan_dates: str,
    service_type_name: str,
    item_id: str,
    arrangement_name: str | None = None,
    key_name: str | None = None,
) -> dict[str, Any]:
    return {
        "id": f"ss-{plan_id}-{item_id}",
        "type": "SongSchedule",
        "attributes": {
            "plan_sort_date": plan_sort_date,
            "plan_dates": plan_dates,
            "service_type_name": service_type_name,
            "arrangement_name": arrangement_name,
            "key_name": key_name,
        },
        "relationships": {
            "plan": {"data": {"id": plan_id, "type": "Plan"}},
            "service_type": {"data": {"id": service_type_id, "type": "ServiceType"}},
            "item": {"data": {"id": item_id, "type": "Item"}},
        },
    }


def add_common_responses(rsps: responses.RequestsMock, *, folder_id: str = "folder-1") -> None:
    rsps.get(
        f"{BASE_URL}/services/v2/folders/{folder_id}/service_types",
        json=payload(
            [
                service_type("st-1", "Sunday AM"),
                service_type("st-2", "Sunday PM"),
            ]
        ),
    )
