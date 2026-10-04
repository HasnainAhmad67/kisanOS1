from __future__ import annotations

from app.core.config import get_settings


def source_registry() -> dict:
    return {
        "version": get_settings().source_registry_version,
        "checked_at": "2026-10-03T00:00:00Z",
        "entries": [
            {
                "id": "open-meteo-api",
                "title": "Open-Meteo forecast API documentation",
                "url": "https://open-meteo.com/en/docs",
                "publisher": "Open-Meteo",
                "geography": "Forecast grid; not a field sensor",
                "evidence_type": "provider output",
                "source_status": "official",
                "claims": ["Weather values only"],
            },
            {
                "id": "regional-cri-context",
                "title": "Irrigation scheduling (wheat)",
                "url": "https://agri.sindh.gov.pk/irrigation",
                "publisher": "Government of Sindh, Agriculture Department",
                "geography": "Sindh; supporting context only",
                "evidence_type": "regional guidance",
                "source_status": "supporting",
                "claims": ["CRI stage context only; no Bahawalpur schedule, timing, amount, or frequency"],
            },
            {
                "id": "vision-model",
                "title": "Configured self-hosted model",
                "url": None,
                "publisher": "Deployment operator",
                "geography": "Not locally validated",
                "evidence_type": "model output",
                "source_status": "unverified",
                "claims": ["Visible signs only; model card, revision and local evaluation required"],
            },
            {
                "id": "amis",
                "title": "Punjab Agriculture Marketing Information Service",
                "url": None,
                "publisher": "Punjab Agriculture Department",
                "geography": "Punjab",
                "evidence_type": "market quote",
                "source_status": "unverified",
                "claims": ["Official current quotes are not enabled because a stable API contract was not verified"],
            },
        ],
        "disclaimer": "Registry references do not establish local agronomic accuracy. Review source terms, publication dates, geography, and claims before deployment.",
    }
