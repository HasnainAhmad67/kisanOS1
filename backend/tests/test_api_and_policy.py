from __future__ import annotations

import asyncio
import time

from fastapi.testclient import TestClient

from app.agents.advisor import build_farm_plan
from app.agents.market import assess_market
from app.agents.water import assess_water
from app.main import app
from app.schemas import AgentResult


def _payload(**overrides):
    data = {
        "crop": "wheat",
        "crop_confirmed": True,
        "area_code": "bahawalpur_sadar",
        "area_confirmed": True,
        "growth_stage": "not_sure",
        "irrigation_history": "not_sure",
        "soil_moisture": "not_sure",
        "drainage": "not_sure",
        "symptom_onset": "recent",
        "symptoms_spreading": "not_sure",
        "symptoms": ["yellowing", "spots"],
        "locale": "en",
        "timezone": "Asia/Karachi",
        "consent_given": True,
        "consent_version": "2026-10-03",
    }
    data.update(overrides)
    return data


def _offline_weather(assessment_id, intake):
    async def result():
        return AgentResult(
            assessment_id=assessment_id,
            agent_id="weather",
            status="unavailable",
            summary="Weather unavailable; no fallback used.",
            evidence_reason="Provider offline.",
            provider_or_model="test",
            version="test",
        )

    return result()


def _offline_vision(assessment_id, intake, images):
    async def result():
        return AgentResult(
            assessment_id=assessment_id,
            agent_id="vision",
            status="not_assessed",
            summary="No model configured.",
            evidence_reason="Test abstention.",
            provider_or_model="test",
            version="test",
        )

    return result()


def test_scope_confirmation_and_consent():
    with TestClient(app) as client:
        bad = client.post("/api/v1/assessments", json=_payload(crop="rice"))
        assert bad.status_code == 422
        no_consent = client.post("/api/v1/assessments", json=_payload(consent_given=False))
        assert no_consent.status_code == 422
        unconfirmed = client.post("/api/v1/assessments", json=_payload(area_confirmed=False))
        assert unconfirmed.status_code == 422
        good = client.post("/api/v1/assessments", json=_payload())
        assert good.status_code == 201
        assert good.json()["assessment_id"]
        assert good.json()["access_token"]


def test_assessment_token_is_required():
    with TestClient(app) as client:
        created = client.post("/api/v1/assessments", json=_payload()).json()
        path = f"/api/v1/assessments/{created['assessment_id']}"
        assert client.get(path).status_code == 401
        assert client.get(path, headers={"X-Assessment-Token": "incorrect"}).status_code == 403
        assert client.get(path, headers={"X-Assessment-Token": created["access_token"]}).status_code == 200


def test_no_market_price_is_invented():
    result = assess_market("00000000-0000-4000-8000-000000000001", {})
    assert result.status == "unavailable"
    assert result.data["quote"] is None
    assert "Price unavailable" in result.summary


def test_water_policy_never_issues_irrigation_instruction():
    result = assess_water(
        "00000000-0000-4000-8000-000000000001",
        {
            "growth_stage": "cri",
            "soil_moisture": "not_sure",
            "drainage": "not_sure",
            "irrigation_history": "not_sure",
            "last_irrigation_date": None,
        },
    )
    assert result.data["irrigation_command"] is None
    assert "CRI" in result.summary
    assert all("irrigate now" not in check.lower() for check in result.checks)


def test_advisor_uses_allowed_statuses_and_caps_checks():
    crop = AgentResult(
        assessment_id="a",
        agent_id="crop",
        status="complete",
        summary="Screening only.",
        observations=["Farmer reported: rust-like marks"],
        possible_causes=["Possible leaf issue"],
        checks=[f"Check {n}" for n in range(8)],
        evidence_reason="Evidence is limited.",
        provider_or_model="rules",
        version="1",
    )
    plan = build_farm_plan(
        "a",
        {
            "symptoms_spreading": "yes",
            "growth_stage": "not_sure",
            "irrigation_history": "not_sure",
            "symptoms": ["spots"],
        },
        [crop],
    )
    assert plan.status == "expert_review_recommended"
    assert len(plan.checks) <= 3
    assert plan.conflicts == []
    assert "not a confirmed diagnosis" in plan.safety_banner.lower()


def test_analysis_returns_five_agent_cards_even_when_providers_are_offline(monkeypatch):
    from app.services import orchestrator

    async def fake_weather(assessment_id, intake):
        return await _offline_weather(assessment_id, intake)

    async def fake_vision(assessment_id, intake, images):
        return await _offline_vision(assessment_id, intake, images)

    monkeypatch.setattr(orchestrator, "assess_weather", fake_weather)
    monkeypatch.setattr(orchestrator, "analyze_images", fake_vision)
    with TestClient(app) as client:
        created = client.post("/api/v1/assessments", json=_payload()).json()
        token = created["access_token"]
        headers = {"X-Assessment-Token": token}
        started = client.post(f"/api/v1/assessments/{created['assessment_id']}/analyze", headers=headers)
        assert started.status_code == 202
        job_id = started.json()["job_id"]
        for _ in range(100):
            job = client.get(f"/api/v1/jobs/{job_id}", headers=headers).json()
            if job["state"] in {"succeeded", "partial", "failed"}:
                break
            time.sleep(0.02)
        assert job["state"] == "partial"
        assert any(event["phase"] == "farm_advisor" for event in job["events"])
        result = client.get(f"/api/v1/assessments/{created['assessment_id']}/results", headers=headers).json()
        assert {card["agent_id"] for card in result["agents"]} == {"weather", "water", "crop", "vision", "market"}
        assert result["farm_plan"]["status"] in {
            "insufficient_information",
            "monitor",
            "field_inspection_recommended",
            "expert_review_recommended",
        }


def test_demo_route_never_inserts_fixture_weather_or_prices():
    with TestClient(app) as client:
        response = client.post("/api/v1/demo/seed")
        assert response.status_code == 201
        assert "SIMULATED INPUT SCENARIO" in response.json()["demo_fixture"]
        assert "no simulated weather" in response.json()["demo_fixture"]


def test_weather_without_provider_timestamp_is_stale(monkeypatch):
    from app.agents.weather import WeatherAgent, assess_weather

    monkeypatch.setattr(
        WeatherAgent,
        "fetch_live_weather",
        lambda self, lat, lon: {
            "timezone": "Asia/Karachi",
            "current": {"temperature_2m": 22, "relative_humidity_2m": 45},
            "daily": {},
        },
    )
    result = asyncio.run(assess_weather("00000000-0000-4000-8000-000000000001", {"area_code": "bahawalpur_sadar"}))
    assert result.status == "stale"
    assert result.data["freshness"] == "stale_or_timestamp_missing"


def test_vision_model_text_safety_gate():
    from app.agents.vision import UNSAFE_MODEL_TEXT

    assert UNSAFE_MODEL_TEXT.search("confirmed diagnosis; apply spray")
    assert not UNSAFE_MODEL_TEXT.search("visible yellowing and a few spots")
