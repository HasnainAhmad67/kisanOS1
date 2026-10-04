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
                "id": "crop-rules",
                "title": "KisanOS deterministic wheat screening rules (backend Crop adapter)",
                "url": None,
                "publisher": "KisanOS backend",
                "geography": "Bahawalpur pilot; not locally validated",
                "evidence_type": "rule-based screening",
                "source_status": "unverified",
                "claims": [
                    "Hypothesis language and farmer-answerable field checks only; no externally verified Crop agronomy source record yet; pending local agronomist review"
                ],
            },
            {
                "id": "vision-symptom-reference",
                "title": "Classification of wheat diseases using deep learning networks with field and glasshouse images",
                "url": "https://pmc.ncbi.nlm.nih.gov/articles/PMC10953319/",
                "publisher": "Plant Pathology (John Wiley & Sons / British Society for Plant Pathology); Long, Hartley, Morris & Brown, John Innes Centre",
                "geography": "UK and Ireland field and glasshouse images; not validated in Punjab or Bahawalpur",
                "evidence_type": "open-access research article (CC BY 4.0)",
                "source_status": "supporting",
                "claims": [
                    "Wheat foliar symptom-class reference and a published field-image classifier evaluation; it does not validate any model deployed here"
                ],
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
                "id": "farmer-market-quote",
                "title": "Farmer-entered market quote (assessment intake)",
                "url": None,
                "publisher": "Farmer (entered via KisanOS)",
                "geography": "Market named by the farmer; not independently verified",
                "evidence_type": "user-supplied market quote",
                "source_status": "farmer_reported",
                "claims": [
                    "Card-level Source on Market cards only; the quote may be stale or wrong and is never presented as official market data"
                ],
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
