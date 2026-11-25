"""Request/response schemas."""
from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator


class AuditRequest(BaseModel):
    url: str = Field(min_length=3, max_length=2048)
    max_pages: int | None = Field(default=None, ge=1, le=25)
    ai: bool = True


class AuditCreatedResponse(BaseModel):
    id: str
    status: str
    url: str
    pollUrl: str


class ShareRequest(BaseModel):
    visibility: Literal["public", "private"] = "public"


class LeadRequest(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    email: str = Field(min_length=5, max_length=254)
    business: str = Field(default="", max_length=160)
    website: str = Field(default="", max_length=2048)
    interest: str = Field(default="", max_length=200)
    message: str = Field(default="", max_length=3000)
    audit_id: str = Field(default="", max_length=64)
    source: str = Field(default="analyzer", max_length=64)
    # honeypot — bots fill this in, humans never see it
    company_website_confirm: str = Field(default="", max_length=200)

    @field_validator("email")
    @classmethod
    def validate_email(cls, value: str) -> str:
        value = value.strip()
        if "@" not in value or "." not in value.split("@")[-1] or " " in value:
            raise ValueError("Please enter a valid work email address.")
        return value

    @field_validator("name", "business", "interest", "message")
    @classmethod
    def strip(cls, value: str) -> str:
        return (value or "").strip()


class LeadResponse(BaseModel):
    ok: bool
    id: str | None = None
    message: str
    delivered: list[str] = []


class ProgressEvent(BaseModel):
    stage: str
    message: str
    percent: int
    at: str
    detail: str | None = None


class AuditStatusResponse(BaseModel):
    id: str
    status: str
    progress: int
    stage: str | None = None
    message: str | None = None
    events: list[ProgressEvent] = []
    report: dict[str, Any] | None = None
    error: str | None = None
    share: dict[str, Any] | None = None
    createdAt: str | None = None
    completedAt: str | None = None
