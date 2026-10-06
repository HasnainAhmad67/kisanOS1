"""Deterministic, fail-closed reader for the official Punjab AMIS price page.

Source
------
Punjab Agriculture Marketing Information Service (AMIS), wheat price page::

    http://www.amis.pk/ViewPrices.aspx?searchType=0&commodityId=1

The page is plain ASP.NET WebForms HTML: a commodity banner (``Commodity:
Wheat`` plus ``[ All Prices are in Rs/100Kg specified otherwise ]``) followed by
one price table whose header row reads ``Dated:<dd-mm-yyyy> | Graph | Min | Max
| FQP | Quantity`` and whose data rows carry the market name in the first
column. The parser below reads only that structure; it never guesses.

Safety rules (non-negotiable)
-----------------------------
* Nothing is ever invented: no price, date, unit, market or source URL is
  synthesised. Any missing/implausible field fails closed -> no quote.
* A row for a different city is never substituted for the requested market.
* ``FQP`` (meaning not published on the page) is **not** treated as an
  average; ``average_price`` is only filled from a column labelled
  "average"/"avg".
* Freshness comes from the AMIS source date only: <= 24h old = ``fresh``,
  older = ``stale``, absent = ``unknown`` (source-reported, not "today").
* The in-memory cache is best effort (Vercel-safe): an entry is dropped after
  its TTL and is never served afterwards, and a cache miss after a failed
  fetch yields no quote at all.

No new dependency: only ``httpx`` (already in requirements.txt) and the stdlib.
"""

from __future__ import annotations

import re
import threading
import time
from datetime import UTC, date, datetime, timedelta, timezone
from html.parser import HTMLParser
from typing import Any

import httpx

from app.core.config import AREAS, get_settings

# --------------------------------------------------------------------- source
SOURCE = "AMIS"
SOURCE_TITLE = "Punjab AMIS daily wheat price"
PUBLISHER = "Punjab Agriculture Marketing Information Service (AMIS)"
SOURCE_URL_LABEL = "Source URL"
USER_AGENT = "KisanOS-MarketAgent/1.0 (official AMIS price reader; contact: kisanos)"
MAX_HTML_BYTES = 2_000_000
MAX_FRESHNESS_SECONDS = 24 * 3600

# Pakistan Standard Time is UTC+05:00 year-round (no DST), so a fixed offset
# keeps the source-date maths deterministic without a tzdata dependency.
SOURCE_TZ = timezone(timedelta(hours=5), "PKT")

# Pilot area -> AMIS market. "Bahawalpur City"/"Bahawalpur Sadar" both mean the
# single AMIS "BahawalPur" market; anything else must match a returned market
# name exactly (normalised) or the fetch fails closed.
MARKET_ALIASES: dict[str, str] = {
    "bahawalpursadar": "Bahawalpur",
    "bahawalpurcity": "Bahawalpur",
    "bahawalpur": "Bahawalpur",
}

_MIN_LABELS = {"min", "min price", "minimum", "minimum price", "min rate"}
_MAX_LABELS = {"max", "max price", "maximum", "maximum price", "max rate"}
_AVG_LABELS = {"average", "avg", "average price", "avg price", "average rate"}
_ROW_LABELS = {"dated", "min", "max", "average", "avg", "graph", "quantity", "total"}

_NUMBER = re.compile(r"\d{1,7}(?:\.\d{1,3})?")
_MISSING_VALUES = {"", "-", "--", "n/a", "na", "null", "not available"}
_DATE_FORMATS = (
    "%d-%m-%Y",
    "%d/%m/%Y",
    "%Y-%m-%d",
    "%d-%b-%Y",
    "%d %b %Y",
    "%d %B %Y",
    "%d-%B-%Y",
)

# ----------------------------------------------------------------- cache state
_CACHE: dict[tuple[str, str], tuple[float, dict[str, Any]]] = {}
_CACHE_LOCK = threading.Lock()
_MAX_CACHE_ENTRIES = 64


# ------------------------------------------------------------------- helpers
def _clean(text: str) -> str:
    """Collapse whitespace and non-breaking spaces; strip the edges."""
    return re.sub(r"\s+", " ", text.replace("\xa0", " ")).strip()


def normalise_market(name: str) -> str:
    """Case/space/punctuation-insensitive market key (never a fuzzy match)."""
    return re.sub(r"[^a-z0-9]", "", name.lower())


def market_target(requested: str) -> str:
    """Display name of the AMIS market a requested market resolves to.

    Only the published aliases are resolved (Bahawalpur Sadar / Bahawalpur
    City -> Bahawalpur). Everything else is used verbatim and must match a
    returned market exactly.
    """
    key = normalise_market(requested)
    if key in MARKET_ALIASES:
        return MARKET_ALIASES[key]
    return _clean(requested)


def requested_market(intake: dict[str, Any]) -> str:
    """Market to ask AMIS for: the pilot area first (authoritative), then the
    farmer-entered market name. Empty string means "nothing to ask for"."""
    area = intake.get("area_code")
    if isinstance(area, str):
        info = AREAS.get(area)
        if info:
            return str(info["name"])
    quote = intake.get("market_quote")
    if isinstance(quote, dict):
        market = quote.get("market")
        if isinstance(market, str) and market.strip():
            return market.strip()
    return ""


# ------------------------------------------------------------------ HTML rows
class _RowParser(HTMLParser):
    """Tolerant cell extractor: every ``<tr>`` in document order, flattened.

    AMIS nests the price table inside a ``<td>`` of an outer row, so row and
    cell boundaries are tracked flat (a new ``<tr>`` simply starts a new row)
    instead of by depth. Table boundaries themselves are ignored: the price
    table is identified later by its header labels.
    """

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.rows: list[list[str]] = []
        self._row: list[str] | None = None
        self._cell: list[str] | None = None

    def _flush_cell(self) -> None:
        if self._cell is not None and self._row is not None:
            self._row.append(_clean("".join(self._cell)))
        self._cell = None

    def _flush_row(self) -> None:
        self._flush_cell()
        # Container rows (an outer <tr> that only wraps a nested table) carry no
        # text of their own and must not become junk rows.
        if self._row and any(_clean(cell) for cell in self._row):
            self.rows.append(self._row)
        self._row = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        tag = tag.lower()
        if tag == "tr":
            # A nested <tr> starts a fresh row of its own.
            self._flush_row()
            self._row = []
        elif tag in {"td", "th"}:
            if self._row is None:
                self._row = []
            if self._cell is None:
                self._cell = []
        elif tag == "br" and self._cell is not None:
            self._cell.append(" ")

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        if tag in {"td", "th"}:
            self._flush_cell()
        elif tag == "tr":
            self._flush_row()

    def handle_data(self, data: str) -> None:
        if self._cell is not None:
            self._cell.append(data)


def extract_rows(html: str) -> list[list[str]]:
    """Rows of every table on the page (best effort, never raises)."""
    parser = _RowParser()
    try:
        parser.feed(html)
        parser.close()
    except Exception:  # noqa: BLE001 - malformed HTML must not escape
        pass
    return parser.rows


# ------------------------------------------------------------- page metadata
def commodity_label(html: str) -> str | None:
    """Commodity the page says it is quoting (``Wheat``), or ``None``."""
    match = re.search(
        r'id=["\']ctl00_cphPage_lblMsg["\']>\s*([^<]{1,60})', html, re.IGNORECASE
    )
    if match:
        return _clean(match.group(1)) or None
    match = re.search(
        r'id=["\']?selectedcommodity["\']?[\s\S]{0,600}?Commodity:\s*([\s\S]{0,300}?)</h2>',
        html,
        re.IGNORECASE,
    )
    if match:
        label = _clean(re.sub(r"<[^>]+>", " ", match.group(1)))
        return _clean(label.split("[", 1)[0]) or None
    return None


def unit_label(html: str) -> str | None:
    """Price unit exactly as the page states it (``Rs/100Kg``), or ``None``."""
    match = re.search(r"All\s+Prices\s+are\s+in\s+([^\]<]{1,40})", html, re.IGNORECASE)
    if not match:
        return None
    unit = _clean(match.group(1))
    unit = _clean(re.sub(r"\s+specified\s+otherwise\s*$", "", unit, flags=re.IGNORECASE))
    return unit or None


def parse_source_date(header_cell: str) -> date | None:
    """``Dated:05-10-2026`` -> date; unparseable/absent -> ``None``."""
    text = re.sub(r"(?i)^dated\s*:\s*", "", _clean(header_cell))
    if not text:
        return None
    for fmt in _DATE_FORMATS:
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    return None


def _price(text: str) -> tuple[float | None, bool]:
    """Parse one price cell -> ``(value, invalid)``.

    ``value is None`` means "not reported" (``-``/empty). ``invalid`` means the
    cell held something that was not a plausible positive price - a hard error.
    """
    raw = _clean(text).lower()
    if raw in _MISSING_VALUES:
        return None, False
    compact = _clean(text).replace(",", "").replace(" ", "")
    if not _NUMBER.fullmatch(compact):
        return None, True
    value = float(compact)
    if value <= 0:
        # AMIS prints "-" for no trade; a literal 0 carries no usable price.
        return None, False
    if value > 1_000_000:
        return None, True
    return value, False


def _header_columns(row: list[str]) -> dict[str, Any] | None:
    """Column map of a price-table header; ``date_col`` may be ``None`` when
    the page carries no ``Dated:`` cell (freshness then reads "unknown")."""
    labels = [_clean(cell).lower().rstrip(":") for cell in row]
    date_col = next((i for i, label in enumerate(labels) if label.startswith("dated")), None)
    min_col = next((i for i, label in enumerate(labels) if label in _MIN_LABELS), None)
    max_col = next((i for i, label in enumerate(labels) if label in _MAX_LABELS), None)
    if min_col is None or max_col is None:
        return None
    avg_col = next((i for i, label in enumerate(labels) if label in _AVG_LABELS), None)
    return {
        "date_col": date_col,
        "min_col": min_col,
        "max_col": max_col,
        "avg_col": avg_col,
        "width": len(row),
    }


def _market_cell_text(cell: str) -> str:
    """``13&nbspBahawalPur`` -> ``BahawalPur`` (leading row index dropped)."""
    return re.sub(r"^\d+\s+", "", _clean(cell))


def _data_rows(rows: list[list[str]], header_index: int, width: int) -> list[list[str]]:
    """Rows of the price table: same width, market name first, no new header."""
    collected: list[list[str]] = []
    for row in rows[header_index + 1 :]:
        if len(row) != width:
            break
        label = _clean(row[0])
        if not label or not re.search(r"[A-Za-z]", label):
            break
        if label.lower().rstrip(":") in _ROW_LABELS:
            break
        collected.append(row)
    return collected


# ------------------------------------------------------------------ fetching
def fetch_html(url: str, timeout: float) -> str:
    """GET the AMIS page with a normal User-Agent and a hard byte cap."""
    headers = {
        "User-Agent": USER_AGENT,
        "Accept": "text/html,application/xhtml+xml",
        "Accept-Language": "en-PK,en;q=0.9",
    }
    with httpx.Client(
        timeout=timeout, headers=headers, follow_redirects=True
    ) as client:
        response = client.get(url)
        response.raise_for_status()
        body = response.content[:MAX_HTML_BYTES]
    encoding = response.encoding or "utf-8"
    try:
        return body.decode(encoding, errors="replace")
    except LookupError:  # pragma: no cover - unknown codec on the wire
        return body.decode("utf-8", errors="replace")


# ------------------------------------------------------------------- parsing
def parse_page(
    html: str,
    *,
    market: str,
    commodity: str,
    source_url: str,
    now: datetime,
) -> tuple[dict[str, Any] | None, str, int]:
    """Parse one AMIS page -> ``(quote | None, problem_code, rows_seen)``.

    Any problem code (non-empty) means "no quote" - fail closed, no partial or
    substituted price is ever returned.
    """
    rows = extract_rows(html)
    rows_seen = len(rows)

    label = commodity_label(html)
    if label is None:
        return None, "amis_commodity_label_missing", rows_seen
    if normalise_market(label) != normalise_market(commodity):
        return None, "amis_commodity_mismatch", rows_seen

    unit = unit_label(html)
    if unit is None:
        return None, "amis_unit_missing", rows_seen
    if not re.search(r"\b(rs|pkr|rupees?)\b", unit, re.IGNORECASE):
        # Currency cannot be established from the source unit: never label it PKR.
        return None, "amis_unit_currency_unsupported", rows_seen

    columns: dict[str, Any] | None = None
    header_index = -1
    for index, row in enumerate(rows):
        columns = _header_columns(row)
        if columns is not None:
            header_index = index
            break
    if columns is None or header_index < 0:
        return None, "amis_price_table_not_found", rows_seen

    date_cell = (
        rows[header_index][columns["date_col"]]
        if columns["date_col"] is not None
        else ""
    )
    source_date = parse_source_date(date_cell)

    target = normalise_market(market_target(market))
    if not target:
        return None, "amis_market_not_requested", rows_seen

    match: tuple[list[str], str] | None = None
    for row in _data_rows(rows, header_index, columns["width"]):
        reported = _market_cell_text(row[0])
        if normalise_market(reported) == target:
            match = (row, reported)
            break
    if match is None:
        # Never substitute another city for the requested market.
        return None, "amis_market_not_returned", rows_seen
    row, reported_market = match

    min_price, min_bad = _price(row[columns["min_col"]])
    max_price, max_bad = _price(row[columns["max_col"]])
    average_price: float | None = None
    if columns["avg_col"] is not None:
        average_price, avg_bad = _price(row[columns["avg_col"]])
        if avg_bad:
            return None, "amis_price_invalid", rows_seen
    if min_bad or max_bad:
        return None, "amis_price_invalid", rows_seen
    if min_price is None and max_price is None and average_price is None:
        return None, "amis_row_has_no_prices", rows_seen
    if min_price is not None and max_price is not None and min_price > max_price:
        return None, "amis_min_greater_than_max", rows_seen

    freshness = _freshness(source_date, now)
    if freshness is None:
        return None, "amis_source_date_in_future", rows_seen

    quote: dict[str, Any] = {
        "source": SOURCE,
        "source_url": source_url,
        "market": market_target(market),
        "market_reported_by_source": reported_market,
        "commodity": _clean(commodity).title() if _clean(commodity).islower() else _clean(commodity),
        "currency": "PKR",
        "unit": unit,
        "min_price": min_price,
        "max_price": max_price,
        "average_price": average_price,
        "quoted_at": (
            datetime(
                source_date.year, source_date.month, source_date.day, tzinfo=SOURCE_TZ
            ).isoformat()
            if source_date
            else None
        ),
        "source_date": source_date.isoformat() if source_date else None,
        "retrieved_at": now.astimezone(UTC).isoformat(),
        "evidence_band": "medium" if freshness == "fresh" else "low",
        "verification_status": "source_reported",
        "freshness": freshness,
    }
    return quote, "", rows_seen


def _freshness(source_date: date | None, now: datetime) -> str | None:
    """``fresh`` / ``stale`` / ``unknown``, or ``None`` when the source date is
    in the future (validation failure -> fail closed)."""
    if source_date is None:
        return "unknown"
    start = datetime(source_date.year, source_date.month, source_date.day, tzinfo=SOURCE_TZ)
    age_seconds = (now - start).total_seconds()
    if age_seconds < 0:
        return None
    return "fresh" if age_seconds <= MAX_FRESHNESS_SECONDS else "stale"


# --------------------------------------------------------------------- cache
def _cache_get(key: tuple[str, str], ttl: int) -> dict[str, Any] | None:
    if ttl <= 0:
        return None
    with _CACHE_LOCK:
        entry = _CACHE.get(key)
        if entry is None:
            return None
        stored_at, quote = entry
        if time.monotonic() - stored_at > ttl:
            # Expired entries are dropped, never served.
            _CACHE.pop(key, None)
            return None
        return dict(quote)


def _cache_put(key: tuple[str, str], quote: dict[str, Any], ttl: int) -> None:
    if ttl <= 0:
        return
    with _CACHE_LOCK:
        if len(_CACHE) >= _MAX_CACHE_ENTRIES:
            _CACHE.clear()
        _CACHE[key] = (time.monotonic(), dict(quote))


def clear_cache() -> None:
    """Drop the in-memory cache (tests / manual refresh)."""
    with _CACHE_LOCK:
        _CACHE.clear()


def _recompute_freshness(quote: dict[str, Any], now: datetime) -> str | None:
    """Re-read freshness for a cached quote: a TTL must never extend a quote's
    freshness, so the source date is re-evaluated against ``now`` every time."""
    source_date = date.fromisoformat(quote["source_date"]) if quote.get("source_date") else None
    freshness = _freshness(source_date, now)
    if freshness is None:
        return None
    quote["freshness"] = freshness
    quote["evidence_band"] = "medium" if freshness == "fresh" else "low"
    return freshness


def _diag(**updates: Any) -> dict[str, Any]:
    return {
        "enabled": False,
        "attempted": False,
        "reason": "",
        "url": "",
        "cache": "bypass",
        "market": "",
        "rows_seen": 0,
        **updates,
    }


def fetch_quote(
    market: str,
    commodity: str,
    *,
    now: datetime | None = None,
) -> tuple[dict[str, Any] | None, dict[str, Any]]:
    """Fetch one AMIS quote for ``market``/``commodity``.

    Returns ``(quote, diagnostics)``; ``quote is None`` means fail-closed and
    ``diagnostics["reason"]`` says why. Never raises: network, HTML, cache and
    configuration failures all collapse into a reason code.
    """
    settings = get_settings()
    now = now or datetime.now(UTC)
    url = str(settings.amis_wheat_url)
    diag = _diag(
        enabled=bool(settings.amis_enabled),
        url=url,
        market=market_target(_clean(market)),
    )

    if not settings.amis_enabled:
        diag["reason"] = "amis_disabled"
        return None, diag
    if not _clean(market):
        diag["reason"] = "amis_market_not_requested"
        return None, diag

    ttl = int(settings.amis_cache_ttl_sec)
    key = (normalise_market(market_target(market)), normalise_market(commodity))

    cached = _cache_get(key, ttl)
    if cached is not None:
        diag["cache"] = "hit"
        if _recompute_freshness(cached, now) is None:
            _cache_clear_key(key)
            diag["reason"] = "amis_source_date_in_future"
            return None, diag
        cached["retrieved_at"] = cached.get("retrieved_at") or now.astimezone(UTC).isoformat()
        return cached, diag

    diag["attempted"] = True
    diag["cache"] = "miss"
    try:
        html = fetch_html(url, float(settings.amis_timeout_sec))
    except Exception as exc:  # noqa: BLE001 - timeout/DNS/TLS/HTTP all fail closed
        diag["reason"] = f"amis_fetch_failed:{type(exc).__name__}"
        return None, diag

    try:
        quote, problem, rows_seen = parse_page(
            html,
            market=market,
            commodity=commodity,
            source_url=url,
            now=now,
        )
    except Exception as exc:  # noqa: BLE001 - parser must never escape
        diag["reason"] = f"amis_parse_failed:{type(exc).__name__}"
        return None, diag

    diag["rows_seen"] = rows_seen
    if quote is None:
        diag["reason"] = problem or "amis_unusable_response"
        return None, diag

    _cache_put(key, quote, ttl)
    return quote, diag


def _cache_clear_key(key: tuple[str, str]) -> None:
    with _CACHE_LOCK:
        _CACHE.pop(key, None)
