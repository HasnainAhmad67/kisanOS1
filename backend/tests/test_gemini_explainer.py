"""Tests for the consent-gated Gemini explanation layer.

Every gate must degrade to a skipped/unavailable AIExplanation without ever
failing the assessment or touching the FarmPlan: consent, enable flag, API
key, timeout, invalid/unsafe responses, count mismatches, injection attempts.
The payload allowlist is verified to carry no photos, GPS, private notes, or
agent summaries.
"""

from __future__ import annotations

import asyncio
import json
from copy import deepcopy
from types import SimpleNamespace
from uuid import uuid4

from pydantic import SecretStr

from app.agents.advisor import SAFETY_BANNER
from app.schemas import AgentResult, FarmCheck, FarmPlan
from app.services import gemini_explainer as gx
from app.services.gemini_explainer import _safe_payload, explain_farm_plan

AID = str(uuid4())


class _FakeModels:
    def __init__(self, text="", delay=0.0, error=None):
        self.text = text
        self.delay = delay
        self.error = error
        self.calls: list[dict] = []

    async def generate_content(self, **kwargs):
        self.calls.append(kwargs)
        if self.delay:
            await asyncio.sleep(self.delay)
        if self.error is not None:
            raise self.error
        return SimpleNamespace(text=self.text)


class _FakeAio:
    def __init__(self, models: _FakeModels):
        self.models = models

    async def aclose(self):
        return None


class _FakeClient:
    def __init__(self, models: _FakeModels):
        self.aio = _FakeAio(models)
        self.closed = False

    def close(self):
        self.closed = True


def _settings(enabled=True, key="fake-key", model="gemini-test", timeout=5.0) -> SimpleNamespace:
    return SimpleNamespace(
        gemini_enabled=enabled,
        gemini_api_key=SecretStr(key) if key is not None else None,
        gemini_model=model,
        gemini_timeout_seconds=timeout,
    )


def _install(monkeypatch, *, text="", delay=0.0, error=None, settings=None) -> _FakeClient:
    """Route genai.Client to a recording fake and settings to a test namespace."""
    client = _FakeClient(_FakeModels(text=text, delay=delay, error=error))
    monkeypatch.setattr(gx, "genai", SimpleNamespace(Client=lambda api_key: client))
    monkeypatch.setattr(gx, "get_settings", lambda: settings or _settings())
    return client


def _install_no_client(monkeypatch, settings=None) -> None:
    """Gates fail before construction: any client build is a test failure."""

    def _forbidden(api_key):
        raise AssertionError("Gemini client must not be constructed when a gate fails")

    monkeypatch.setattr(gx, "genai", SimpleNamespace(Client=_forbidden))
    monkeypatch.setattr(gx, "get_settings", lambda: settings or _settings())


def _plan(check_count=2) -> FarmPlan:
    checks = [
        FarmCheck(
            id=f"check-{n + 1}",
            priority=n + 1,
            title=f"Compare plant number {n + 1} with a healthy-looking area",
            how_to_check="Repeat the check on several plants.",
            why="Evidence is limited; possibilities remain unconfirmed.",
            what_to_observe="What you actually see at each spot.",
            evidence_labels=["crop"],
        )
        for n in range(check_count)
    ]
    return FarmPlan(
        status="field_inspection_recommended",
        rationale="Available reports support a small set of direct field checks; they do not establish a cause or prescribe an action.",
        agent_summary={"crop": "Screening only."},
        checks=checks,
        verification_step="Record what you observed after checking; if signs spread, ask a local agriculture officer to review them.",
        conflicts=[],
        safety_banner=SAFETY_BANNER,
        policy_version="kisanos-safe-policy-1.0.0",
    )


def _intake(**overrides) -> dict:
    base = {
        "locale": "en",
        "crop": "wheat",
        "area_code": "bahawalpur_sadar",
        "growth_stage": "tillering",
        "symptoms": ["yellowing"],
        "gemini_explanation_consent": True,
    }
    base.update(overrides)
    return base


def _agents() -> list[AgentResult]:
    return [
        AgentResult(
            assessment_id=AID,
            agent_id="crop",
            status="complete",
            summary="Screening only; possibilities remain unconfirmed.",
            observations=["Farmer reported yellowing on lower leaves"],
            checks=["Compare older and younger leaves"],
            evidence_reason="Evidence is limited.",
            provider_or_model="rules",
            version="test",
        )
    ]


def _narration(check_count=2, **overrides) -> str:
    payload = {
        "farmer_summary": "Your plan asks you to compare plants by hand.",
        "evidence_explanation": "The reports describe visible signs only and cannot establish a cause.",
        "check_explanations": [f"Look at plant {n + 1} and note what you see." for n in range(check_count)],
    }
    payload.update(overrides)
    return json.dumps(payload)


def _run(intake: dict, plan: FarmPlan):
    return asyncio.run(explain_farm_plan(intake, _agents(), plan))


# ---------------------------------------------------------------- 1. consent
def test_consent_missing_skips_explanation(monkeypatch):
    _install_no_client(monkeypatch)  # enabled + keyed, but consent decides first
    result = _run(_intake(gemini_explanation_consent=False), _plan())
    assert result.status == "skipped"
    assert result.reason == "consent_missing"
    assert result.farmer_summary is None

    # Consent gate wins even when the feature is also disabled.
    _install_no_client(monkeypatch, settings=_settings(enabled=False))
    order = _run(_intake(gemini_explanation_consent=False), _plan())
    assert order.reason == "consent_missing"


# --------------------------------------------------------------- 2. disabled
def test_disabled_flag_skips_explanation(monkeypatch):
    _install_no_client(monkeypatch, settings=_settings(enabled=False))
    result = _run(_intake(locale="ur"), _plan())
    assert result.status == "skipped"
    assert result.reason == "disabled"
    assert result.locale == "ur"


# ------------------------------------------------------------- 3. missing key
def test_missing_api_key_degrades_to_unavailable(monkeypatch):
    for key in (None, "", "   "):
        _install_no_client(monkeypatch, settings=_settings(key=key))
        result = _run(_intake(), _plan())
        assert result.status == "unavailable", key
        assert result.reason == "key_missing", key
        assert result.farmer_summary is None


# ----------------------------------------------------------------- 4. timeout
def test_timeout_degrades_gracefully(monkeypatch):
    client = _install(monkeypatch, text=_narration(), delay=1.0, settings=_settings(timeout=0.05))
    result = _run(_intake(), _plan())
    assert result.status == "unavailable"
    assert result.reason == "timeout"
    assert client.aio.models.calls  # the request really was attempted
    assert client.closed  # cleanup still ran


# -------------------------------------------------------------- 5. invalid
def test_invalid_gemini_responses_are_graceful_skips(monkeypatch):
    plan = _plan(check_count=2)
    cases = [
        "",  # empty response text
        "<html>not json</html>",  # malformed body
        json.dumps({"farmer_summary": "Only one field."}),  # missing fields
        json.dumps(  # count mismatch with plan.checks
            {
                "farmer_summary": "sum",
                "evidence_explanation": "evi",
                "check_explanations": ["only one explanation"],
            }
        ),
        json.dumps({"farmer_summary": "", "evidence_explanation": "evi", "check_explanations": ["a", "b"]}),
    ]
    for text in cases:
        client = _install(monkeypatch, text=text)
        result = _run(_intake(), plan)
        assert result.status == "unavailable", repr(text)
        assert result.reason == "invalid_output", repr(text)
        assert result.check_explanations == []
        assert client.closed


def test_provider_error_is_graceful_skip(monkeypatch):
    client = _install(monkeypatch, error=ValueError("sdk exploded"))
    result = _run(_intake(), _plan())
    assert result.status == "unavailable"
    assert result.reason == "provider_error"
    assert client.closed


# ----------------------------------------------------------------- 6. valid
def test_valid_narration_matches_farm_checks(monkeypatch):
    plan = _plan(check_count=3)
    client = _install(monkeypatch, text=_narration(3))
    result = _run(_intake(), plan)
    assert result.status == "complete"
    assert len(result.check_explanations) == len(plan.checks) == 3
    assert result.model == "gemini-test"
    assert result.generated_at is not None
    assert result.locale == "en"
    assert len(result.farmer_summary) <= 500
    assert all(len(item) <= 260 for item in result.check_explanations)
    assert result.disclaimer

    # Temperature and token limits are enforced on the request.
    call = client.aio.models.calls[0]
    assert call["model"] == "gemini-test"
    assert call["config"].temperature == 0.2
    assert call["config"].max_output_tokens == 900


# ------------------------------------------------------------ 7. payload
def test_payload_never_contains_photos_gps_or_private_notes(monkeypatch):
    plan = _plan()
    intake = _intake(
        notes="Private family note: phone number 03001234567",
        latitude=29.3956,
        longitude=71.6836,
        gps_consent=True,
        symptoms=["yellowing", "made_up_symptom_code"],
    )
    payload = _safe_payload(intake, _agents(), plan)
    assert set(payload) == {
        "locale",
        "crop",
        "coarse_area_code",
        "growth_stage",
        "symptom_codes",
        "agent_statuses",
        "farm_advisor",
    }
    serial = json.dumps(payload, ensure_ascii=False)
    assert "03001234567" not in serial and "Private family" not in serial
    assert "29.3956" not in serial and "71.6836" not in serial
    assert "latitude" not in payload and "notes" not in payload
    assert payload["symptom_codes"] == ["yellowing"]  # allowlist enforced
    assert payload["agent_statuses"] == {"crop": "complete"}  # statuses only
    assert "Screening only" not in serial  # no raw agent summaries
    assert "image_ids" not in serial and "data:image" not in serial  # no photo material

    # Same guarantees over the wire: the request body is the allowlisted payload.
    client = _install(monkeypatch, text=_narration())
    _run(intake, plan)
    request_text = client.aio.models.calls[0]["contents"]
    assert "03001234567" not in request_text
    assert "29.3956" not in request_text
    assert "Private family" not in request_text


# ----------------------------------------------------- 8. cannot alter plan
def test_gemini_cannot_alter_the_farm_plan(monkeypatch):
    plan = _plan(check_count=2)
    before = deepcopy(plan.model_dump())
    client = _install(monkeypatch, text=_narration(2))
    result = _run(_intake(), plan)
    assert result.status == "complete"
    assert plan.model_dump() == before
    assert client.closed

    # Injection attempt: extra fields trying to rewrite the plan are rejected
    # by the strict narration schema (extra=forbid) and never leak out.
    injected = json.dumps(
        {
            "farmer_summary": "sum",
            "evidence_explanation": "evi",
            "check_explanations": ["one", "two"],
            "status": "monitor",
            "checks": [{"id": "check-99", "title": "rewritten check"}],
        }
    )
    client2 = _install(monkeypatch, text=injected)
    plan2 = _plan(check_count=2)
    before2 = deepcopy(plan2.model_dump())
    result2 = _run(_intake(), plan2)
    assert plan2.model_dump() == before2
    assert result2.status == "unavailable"
    assert result2.reason == "invalid_output"
    assert "monitor" not in json.dumps(result2.model_dump())
    assert "check-99" not in json.dumps(result2.model_dump())
    assert client2.closed


# -------------------------------------------------------------- 9. unsafe
def test_unsafe_gemini_wording_is_rejected(monkeypatch):
    plan = _plan(check_count=2)
    unsafe_texts = [
        _narration(2, farmer_summary="Spray pesticide immediately to cure the rust."),
        _narration(2, check_explanations=["Apply urea at a high dose now.", "Look at plant 2."]),
        _narration(2, evidence_explanation="This is a confirmed disease and you should irrigate now."),
        _narration(2, check_explanations=["Check plant 1.", "This yield is guaranteed to double."]),
    ]
    for text in unsafe_texts:
        client = _install(monkeypatch, text=text)
        result = _run(_intake(), plan)
        assert result.status == "unavailable", text
        assert result.reason == "invalid_output", text
        assert result.check_explanations == []
        assert client.closed

    # Negated safety wording is allowed: the scan is not over-eager.
    negated = _narration(
        2,
        farmer_summary="Do not apply chemicals based only on this screen; do not spray anything.",
    )
    client = _install(monkeypatch, text=negated)
    result = _run(_intake(), plan)
    assert result.status == "complete", result
    assert client.closed
