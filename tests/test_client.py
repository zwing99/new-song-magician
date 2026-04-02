from __future__ import annotations

from urllib.parse import parse_qs, urlparse

import click
import pytest
import requests
import responses
from conftest import payload

from new_song_magician.cli import BASE_URL
from new_song_magician.client import PCOClient
from new_song_magician.models import Config


def test_client_requires_auth_credentials() -> None:
    with pytest.raises(click.UsageError) as exc_info:
        PCOClient(
            Config(
                app_id=None,
                secret=None,
                token=None,
                base_url=BASE_URL,
                timeout=30.0,
                gmail_credentials_file="gmail-oauth-client-secret.json",
                gmail_token_file=".gmail-token.json",
                gmail_from=None,
            )
        )

    assert "Provide either --token / PCO_TOKEN" in str(exc_info.value)


@responses.activate
def test_get_json_raises_click_exception_on_api_error(api: PCOClient) -> None:
    responses.get(
        f"{BASE_URL}/services/v2/folders",
        status=500,
        body='{"error":"boom"}',
        content_type="application/json",
    )

    with pytest.raises(click.ClickException) as exc_info:
        api.get_json("/services/v2/folders")

    assert "PCO API error 500" in str(exc_info.value)


@responses.activate
def test_paginate_requests_multiple_offsets(api: PCOClient) -> None:
    seen_offsets: list[str] = []

    def paged_callback(
        request: requests.PreparedRequest,
    ) -> tuple[int, dict[str, str], str]:
        query = parse_qs(urlparse(request.url).query)
        offset = query["offset"][0]
        seen_offsets.append(offset)

        if offset == "0":
            body = payload([{"id": "a"}, {"id": "b"}], count=3)
        elif offset == "2":
            body = payload([{"id": "c"}], count=3)
        else:
            raise AssertionError(f"Unexpected offset {offset}")

        return (200, {"Content-Type": "application/json"}, __import__("json").dumps(body))

    responses.add_callback(
        responses.GET,
        f"{BASE_URL}/paged",
        callback=paged_callback,
        content_type="application/json",
    )

    rows = list(api.paginate("/paged", params={"per_page": 2}))

    assert [row["id"] for row in rows] == ["a", "b", "c"]
    assert seen_offsets == ["0", "2"]
