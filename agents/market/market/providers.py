"""Price-data providers for the KisanOS Market Agent.

The agent never invents prices. Prices come from a provider:
  FilePriceProvider   REAL prices that someone copied from an official source into a JSON / CSV file
                      (every record must carry unit, price date, source URL and retrieved_at)
  SamplePriceProvider bundled MOCK prices (data/sample_prices.json) - always labelled SAMPLE, never real
  NullProvider        no data -> the agent returns "unavailable"
Any object with  fetch(crop, now) -> ProviderResult  can be plugged in (e.g. a DB or AMIS connector).
"""
import csv
import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path

try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:                       # python-dotenv is optional
    pass

try:
    from .schema import find_advice, find_unsafe
except ImportError:                     # running directly from the agent folder
    from schema import find_advice, find_unsafe

DATA_DIR = Path(__file__).parent / "data"
SAMPLE_FILE = DATA_DIR / "sample_prices.json"
CURRENCY = "PKR"
SOURCE_STATUSES = ("official", "supporting", "secondary", "unverified")

# canonical unit -> kg per priced quantity
UNIT_KG = {"per 40 kg": 40.0, "per kg": 1.0, "per 100 kg": 100.0}
_UNIT_ALIASES = {
    "40kg": "per 40 kg", "maund": "per 40 kg", "mann": "per 40 kg", "40kgmaund": "per 40 kg",
    "kg": "per kg", "1kg": "per kg", "kilo": "per kg",
    "100kg": "per 100 kg", "quintal": "per 100 kg",
}
# Sanity range, PKR per kg, to catch unit mistakes (e.g. a per-kg price typed as per-40-kg).
# Tunable default - NOT from a source.
PLAUSIBLE_PER_KG = {"wheat": (20.0, 500.0)}


class ProviderResult:
    def __init__(self, records=None, skipped=None, note="", error=False):
        self.records, self.skipped, self.note, self.error = records or [], skipped or [], note, error


def normalize_unit(text):
    """'PKR per 40 kg', 'Rs/maund', 'per kg' ... -> 'per 40 kg' | 'per kg' | 'per 100 kg' | None."""
    if not isinstance(text, str):
        return None
    key = re.sub(r"[^a-z0-9]", "", text.lower())
    key = re.sub(r"^(pkr|rs|rupees?|rupay)", "", key)
    key = key[3:] if key.startswith("per") else key
    return _UNIT_ALIASES.get(key)


def parse_dt(text):
    """'2026-10-02' or '2026-10-02T09:30:00Z' -> (aware datetime, has_time) or (None, False)."""
    if not isinstance(text, str):
        return None, False
    t = text.strip()
    try:
        if re.fullmatch(r"\d{4}-\d{2}-\d{2}", t):
            return datetime.strptime(t, "%Y-%m-%d").replace(tzinfo=timezone.utc), False
        if re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z", t):
            return datetime.strptime(t, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc), True
    except ValueError:
        pass
    return None, False


def _num(x):
    if isinstance(x, bool) or x is None:
        return None
    try:
        v = float(str(x).replace(",", "").strip())
    except ValueError:
        return None
    return v if v == v and abs(v) != float("inf") else None


def parse_record(raw, now):
    """Validate one raw record. Returns (record, None) or (None, reason)."""
    if not isinstance(raw, dict):
        return None, "record is not an object"
    sample = str(raw.get("is_sample", False)).strip().lower() in ("true", "1", "yes")
    for k in ("crop", "market", "price", "unit"):
        if raw.get(k) in (None, ""):
            return None, f"missing '{k}'"
    crop, market = str(raw["crop"]).strip().lower(), str(raw["market"]).strip()
    district = str(raw["district"]).strip() if raw.get("district") else None
    price = _num(raw["price"])
    if price is None or price <= 0:
        return None, "price must be a positive number"
    pmin, pmax = _num(raw.get("price_min")), _num(raw.get("price_max"))
    if (raw.get("price_min") not in (None, "") and pmin is None) or (raw.get("price_max") not in (None, "") and pmax is None):
        return None, "price_min / price_max must be numbers"
    if (pmin is not None and pmin > price) or (pmax is not None and pmax < price):
        return None, "price must lie between price_min and price_max"
    if str(raw.get("currency", CURRENCY)).strip().upper() != CURRENCY:
        return None, f"currency must be {CURRENCY}"
    unit = normalize_unit(raw["unit"])
    if unit is None:
        return None, f"unit '{raw['unit']}' not recognised (use PKR per 40 kg, PKR per kg or PKR per 100 kg)"
    per_kg = price / UNIT_KG[unit]
    lo, hi = PLAUSIBLE_PER_KG.get(crop, (0.0, float("inf")))
    if not lo <= per_kg <= hi:
        return None, f"price is not plausible for {crop} ({per_kg:.1f} PKR/kg): check the unit"

    price_dt, has_time = parse_dt(raw.get("price_date"))
    if raw.get("price_date") not in (None, "") and price_dt is None:
        return None, "price_date must be YYYY-MM-DD or YYYY-MM-DDTHH:MM:SSZ"
    if price_dt is not None and price_dt > now:
        return None, "price_date is in the future"
    if price_dt is None and not sample:
        return None, "missing 'price_date' (real prices must carry a date)"

    src = {k: str(raw.get(k) or "").strip() for k in ("source_title", "source_url", "publisher")}
    status = str(raw.get("source_status") or "unverified").strip().lower()
    if status not in SOURCE_STATUSES:
        return None, f"source_status must be one of {SOURCE_STATUSES}"
    rt_text = str(raw.get("retrieved_at") or "").strip()
    if sample:
        status = "unverified"
        rt_text = rt_text or now.strftime("%Y-%m-%dT%H:%M:%SZ")
        src["source_title"] = src["source_title"] or "SAMPLE (mock) price data - not a real market source"
        src["source_url"] = src["source_url"] or "https://example.com/kisanos-sample-data-not-real"
        src["publisher"] = src["publisher"] or "KisanOS demo (mock data)"
    else:
        for k in ("source_title", "source_url", "publisher"):
            if not src[k]:
                return None, f"missing '{k}' (real prices must name their source)"
        if not rt_text:
            return None, "missing 'retrieved_at' (when the price was fetched / copied)"
    if not src["source_url"].startswith(("http://", "https://")):
        return None, "source_url must start with http:// or https://"
    rt_dt, _ = parse_dt(rt_text)
    if rt_dt is None or not rt_text.endswith("Z") or "T" not in rt_text:
        return None, "retrieved_at must look like 2026-10-03T12:00:00Z"
    if rt_dt > now:
        return None, "retrieved_at is in the future"
    if price_dt is not None and rt_dt.date() < price_dt.date():
        return None, "retrieved_at is earlier than price_date"

    for text in [market, district or "", *src.values()]:
        if find_unsafe(text) or find_advice(text):
            return None, "text contains a banned keyword"
    provider = "amis" if str(raw.get("provider", "")).strip().lower() == "amis" else "self-hosted"
    return {"crop": crop, "market": market, "district": district, "price": price, "price_min": pmin,
            "price_max": pmax, "unit": unit, "price_per_kg": per_kg, "price_dt": price_dt,
            "price_has_time": has_time, "price_date_text": str(raw["price_date"]).strip() if price_dt else None,
            "source_title": src["source_title"], "source_url": src["source_url"], "publisher": src["publisher"],
            "source_status": status, "retrieved_at": rt_text, "provider": provider, "is_sample": sample}, None


def _collect(raw_records, crop, now):
    records, skipped = [], []
    for i, raw in enumerate(raw_records):
        rec, err = parse_record(raw, now)
        if err:
            skipped.append(f"record {i + 1}: {err}")
        elif rec["crop"] == crop:
            records.append(rec)
    return records, skipped


class NullProvider:
    def fetch(self, crop, now):
        return ProviderResult(note="no price data source is configured")


class FilePriceProvider:
    """Reads REAL prices from a .json ({"records": [...]} or a list) or .csv file."""
    def __init__(self, path):
        self.path = Path(path)

    def fetch(self, crop, now):
        try:
            if self.path.suffix.lower() == ".csv":
                with open(self.path, newline="", encoding="utf-8-sig") as f:
                    raw = list(csv.DictReader(f))
            else:
                data = json.loads(self.path.read_text(encoding="utf-8"))
                raw = data.get("records", []) if isinstance(data, dict) else data
            if not isinstance(raw, list):
                raise ValueError("records must be a list")
        except FileNotFoundError:
            return ProviderResult(note="price file not found", error=True)
        except (OSError, ValueError) as e:             # includes json.JSONDecodeError
            return ProviderResult(note=f"price file could not be read ({type(e).__name__})", error=True)
        records, skipped = _collect(raw, crop, now)
        return ProviderResult(records, skipped, f"{len(raw)} record(s) read from the price file")


class SamplePriceProvider:
    """Bundled MOCK prices. Every record is forced to is_sample = True."""
    def __init__(self, path=SAMPLE_FILE):
        self.path = Path(path)

    def fetch(self, crop, now):
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8")).get("records", [])
        except (OSError, ValueError, AttributeError):
            return ProviderResult(note="sample data file could not be read", error=True)
        records, skipped = _collect([{**r, "is_sample": True} for r in raw if isinstance(r, dict)], crop, now)
        return ProviderResult(records, skipped, "bundled SAMPLE (mock) data")


def default_provider(use_sample=False):
    """Real file (MARKET_PRICE_FILE) if configured, else sample ONLY when asked for, else no data."""
    path = os.environ.get("MARKET_PRICE_FILE")
    if path:
        return FilePriceProvider(path)
    if use_sample or os.environ.get("MARKET_USE_SAMPLE", "").strip() == "1":
        return SamplePriceProvider()
    return NullProvider()
