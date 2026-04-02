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


@dataclass
class SongHistory:
    last_played_at: datetime | None
    last_plan_dates: str | None
    last_service_type_name: str | None
    last_plan_id: str | None
    last_item_id: str | None


@dataclass
class PlanSongReport:
    service_type_id: str
    service_type_name: str
    plan_id: str
    plan_title: str
    sort_date: datetime | None
    song_id: str
    song_title: str
    needs_review: bool
    last_played_at: datetime | None
    last_plan_dates: str | None
    last_service_type_name: str | None
    last_plan_id: str | None
    last_item_id: str | None
