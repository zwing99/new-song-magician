from __future__ import annotations

import base64
from collections.abc import Iterable
from typing import Any

import click
import httpx

from .models import Config


class PCOClient:
    def __init__(self, config: Config) -> None:
        headers = {
            "Accept": "application/json",
            "User-Agent": "new-song-magician/0.1.0",
        }

        if config.token:
            headers["Authorization"] = f"Bearer {config.token}"
        elif config.app_id and config.secret:
            raw = f"{config.app_id}:{config.secret}".encode()
            headers["Authorization"] = "Basic " + base64.b64encode(raw).decode("ascii")
        else:
            raise click.UsageError(
                "Provide either --token / PCO_TOKEN or both "
                "--app-id / PCO_APP_ID and --secret / PCO_SECRET."
            )

        self.client = httpx.Client(
            base_url=config.base_url,
            headers=headers,
            timeout=config.timeout,
        )

    def close(self) -> None:
        self.client.close()

    def get_json(self, path: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        response = self.client.get(path, params=params)
        if response.status_code >= 400:
            raise click.ClickException(
                f"PCO API error {response.status_code} for {response.request.url}\n{response.text}"
            )
        return response.json()

    def paginate(
        self,
        path: str,
        params: dict[str, Any] | None = None,
    ) -> Iterable[dict[str, Any]]:
        page_params = dict(params or {})
        page_params.setdefault("per_page", 100)
        offset = 0

        while True:
            current_params = dict(page_params)
            current_params["offset"] = offset
            payload = self.get_json(path, current_params)
            rows = payload.get("data", [])

            yield from rows

            meta = payload.get("meta", {}) or {}
            count = meta.get("count")
            next_offset = offset + len(rows)

            if not rows:
                break
            if count is not None and next_offset >= count:
                break
            if len(rows) < current_params["per_page"]:
                break

            offset = next_offset
