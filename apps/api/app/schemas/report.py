"""모닝리포트/테마 스코어 스키마. 설계서 §7.2."""
from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, ConfigDict


class MorningReportOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    report_id: str
    report_date: date
    scope: str
    version: int
    status: str
    blocked: bool
    markdown: str
    sections: dict | None = None
    model: str | None = None
    cost_usd: float = 0.0
    disclaimer_version: str | None = None
    created_at: datetime | None = None


class ReportListItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    report_id: str
    report_date: date
    scope: str
    status: str
    blocked: bool
    created_at: datetime | None = None


class GenerateReportRequest(BaseModel):
    report_date: date | None = None
    force: bool = False


class GenerateReportResponse(BaseModel):
    report_date: date
    scope: str
    status: str  # accepted


class ThemeScoreOut(BaseModel):
    theme: str
    slug: str
    score: float
    rank: int
    percentile: float
    components: dict | None = None
    as_of: str
    weights_version: str
