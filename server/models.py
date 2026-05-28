"""Pydantic request/response schemas for Kiwi HTTP API."""

from typing import Any, Optional

from pydantic import BaseModel, Field


class ScanRequest(BaseModel):
    path: str = "."
    severity: str = "ALL"
    platform: Optional[str] = None
    scope: Optional[str] = None
    diff_only: bool = False
    max_per_lesson: int = 5


class CheckRequest(BaseModel):
    file: Optional[str] = None
    files: Optional[list[str]] = None
    severity: str = "CRITICAL"
    platform: Optional[str] = None
    compact: bool = True


class ContextRequest(BaseModel):
    task: str = ""
    scope_type: str = "plugin"
    platform: str = "wp"
    files: Optional[list[str]] = None
    target_file: str = ""
    compact: bool = False


class FixRequest(BaseModel):
    lesson_id: str
    file: Optional[str] = None
    line: int = 0
    apply: bool = False


class DismissRequest(BaseModel):
    lesson_id: str
    file: str
    reason: str
    scope: str = "file"


class QueryRequest(BaseModel):
    keyword: Optional[str] = None
    category: Optional[str] = None
    severity: Optional[str] = None
    platform: Optional[str] = None
    limit: int = 10


class UpgradeRequest(BaseModel):
    tier: str
    license_key: Optional[str] = None


class TrendsRequest(BaseModel):
    path: str
    days: int = 30


class KiwiResponse(BaseModel):
    status: str = "ok"
    data: Any = None


class KiwiError(BaseModel):
    status: str = "error"
    error: dict = Field(default_factory=dict)