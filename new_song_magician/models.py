from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass
class Config:
    app_id: str | None
    secret: str | None
    token: str | None
    base_url: str
    timeout: float
    gmail_credentials_file: str
    gmail_token_file: str
    gmail_from: str | None


@dataclass
class SongHistory:
    last_played_at: datetime | None
    last_plan_dates: str | None
    last_service_type_name: str | None
    arrangement_name: str | None
    key_name: str | None
    last_plan_id: str | None
    last_item_id: str | None


@dataclass
class AttachmentLink:
    name: str
    url: str | None


@dataclass
class PlanSongReport:
    service_type_id: str
    service_type_name: str
    plan_id: str
    plan_title: str
    sort_date: datetime | None
    song_id: str | None
    song_title: str | None
    arrangement_id: str | None
    arrangement_name: str | None
    key_name: str | None
    original_key: str | None
    recent_keys: tuple[str, ...]
    key_comparison: str | None
    needs_review: bool
    last_played_at: datetime | None
    last_plan_dates: str | None
    last_service_type_name: str | None
    last_plan_id: str | None
    last_item_id: str | None
    report_type: str = "song"
    item_title: str | None = None
    item_key_is_set: bool | None = None
    attachment_links: tuple[AttachmentLink, ...] = ()
