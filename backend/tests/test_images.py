from __future__ import annotations

import io

from fastapi.testclient import TestClient
from PIL import Image

from app.main import app


def _payload():
    return {
        "crop": "wheat",
        "crop_confirmed": True,
        "area_code": "bahawalpur_sadar",
        "area_confirmed": True,
        "growth_stage": "not_sure",
        "irrigation_history": "not_sure",
        "soil_moisture": "not_sure",
        "drainage": "not_sure",
        "symptom_onset": "not_sure",
        "symptoms_spreading": "not_sure",
        "symptoms": [],
        "locale": "en",
        "timezone": "Asia/Karachi",
        "consent_given": True,
        "consent_version": "2026-10-03",
    }


def test_upload_signature_validation_and_private_exif_stripped():
    with TestClient(app) as client:
        created = client.post("/api/v1/assessments", json=_payload()).json()
        headers = {"X-Assessment-Token": created["access_token"]}
        rejected = client.post(
            f"/api/v1/assessments/{created['assessment_id']}/images",
            headers=headers,
            data={"view_type": "symptom_closeup"},
            files={"file": ("fake.jpg", b"not an image", "image/jpeg")},
        )
        assert rejected.status_code == 415
        image = Image.new("RGB", (800, 800), (45, 120, 30))
        buffer = io.BytesIO()
        image.save(buffer, format="JPEG")
        uploaded = client.post(
            f"/api/v1/assessments/{created['assessment_id']}/images",
            headers=headers,
            data={"view_type": "symptom_closeup"},
            files={"file": ("leaf.jpg", buffer.getvalue(), "image/jpeg")},
        )
        assert uploaded.status_code == 201
        body = uploaded.json()
        assert body["private_storage"] is True
        assert body["exif_removed"] is True
        assert body["mime_type"] == "image/jpeg"
