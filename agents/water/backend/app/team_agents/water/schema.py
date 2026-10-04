"""Strict shared agent-envelope schema for the KisanOS Water Agent."""

from __future__ import annotations

import re
import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, ValidationError, field_validator

ISO_Z = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")
UNSAFE_TEXT = re.compile(
    r"\b(pesticides?|fungicides?|insecticides?|herbicides?|chemicals?|spray(?:ed|ing)?|doses?|dosage|"
    r"fertili[sz]ers?|urea|dap|npk|potash|nitrogen|imidacloprid|propiconazole|tebuconazole|"
    r"khaad|khad|dawai|dawa|keera\s?maar)\b|(?:کیڑے\s?مار|سپرے|کھاد|زرعی دوا|دوائی|ڈوز)",
    re.IGNORECASE,
)


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, str_strip_whitespace=True)


class Source(StrictModel):
    title: str
    url: str
    publisher: str
    retrieved_at: str
    source_status: Literal["official", "supporting", "secondary", "unverified"]

    @field_validator("url")
    @classmethod
    def require_http_url(cls, value: str) -> str:
        if not value.startswith(("http://", "https://")):
            raise ValueError("source URL must use HTTP or HTTPS")
        return value

    @field_validator("retrieved_at")
    @classmethod
    def require_utc_timestamp(cls, value: str) -> str:
        if not ISO_Z.fullmatch(value):
            raise ValueError("retrieved_at must use UTC ISO-8601 ending in Z")
        datetime.fromisoformat(value)
        return value


class AgentOutput(StrictModel):
    agent_id: Literal["weather", "water", "vision", "crop", "market"]
    assessment_id: str
    status: Literal["complete", "partial", "unavailable", "error"]
    summary: str
    observations: list[str]
    possible_causes: list[str]
    checks: list[str]
    evidence_band: Literal["low", "medium", "high", "not_calibrated"]
    evidence_reason: str
    sources: list[Source]
    provider_or_model: str
    version: str
    created_at: str
    safety_flags: list[str]

    @field_validator("assessment_id")
    @classmethod
    def require_uuid(cls, value: str) -> str:
        uuid.UUID(value)
        return value

    @field_validator("created_at")
    @classmethod
    def require_created_at_utc(cls, value: str) -> str:
        if not ISO_Z.fullmatch(value):
            raise ValueError("created_at must use UTC ISO-8601 ending in Z")
        datetime.fromisoformat(value)
        return value

    @field_validator("summary", "evidence_reason")
    @classmethod
    def require_nonempty_text(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("text must not be empty")
        return value


def _all_strings(value):
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for key, item in value.items():
            yield from _all_strings(key)
            yield from _all_strings(item)
    elif isinstance(value, (list, tuple)):
        for item in value:
            yield from _all_strings(item)


def find_unsafe(text: str) -> str | None:
    match = UNSAFE_TEXT.search(text)
    return match.group(0) if match else None


def validate_output(payload: dict) -> list[str]:
    """Return validation problems; an empty list means the envelope is valid."""
    problems: list[str] = []
    try:
        AgentOutput.model_validate(payload)
    except ValidationError as exc:
        problems.append(str(exc))
    for text in _all_strings(payload):
        unsafe = find_unsafe(text)
        if unsafe:
            problems.append(f"unsafe language is not allowed: {unsafe}")
            break
    return problems
