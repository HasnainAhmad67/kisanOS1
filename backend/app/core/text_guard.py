"""Deterministic unsafe-language guard for the Farm Advisor and the Gemini
explanation layer.

Both layers only rephrase text that other, validated layers produced - but as
defense in depth they must never emit (or repeat) chemical recommendations,
doses, imperative irrigation commands, affirmative disease confirmations,
guarantees, or trading language, even if upstream text slips through.

Matching is deliberately negation-aware: a phrase preceded by a negation
("Do not apply chemicals ...") is allowed, so safety disclaimers such as the
FarmPlan banner and compliant Gemini narration are not rejected.
"""

from __future__ import annotations

import re

_UNSAFE_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    (
        "chemical",
        re.compile(
            r"\b(?:pesticide|fungicide|insecticide|herbicide|acaricide|nematicide|"
            r"fertilizer|fertiliser|urea|npk|micronutrient|chemical|dose|dosage)s?\b",
            re.IGNORECASE,
        ),
    ),
    (
        "chemical_action",
        re.compile(
            r"\b(?:spray|spraying|dose|dosing|apply|applying)\b[^.;!?]{0,60}\b"
            r"(?:chemical|pesticide|fungicide|insecticide|herbicide|medicine|drug|"
            r"urea|fertilizer|fertiliser)\w*\b",
            re.IGNORECASE,
        ),
    ),
    (
        "irrigation_command",
        re.compile(
            r"\birrigate\s+(?:now|today|immediately|right\s+away)\b|"
            r"\b(?:apply|water|irrigate)\s+\d+(?:\.\d+)?\s*(?:mm|ml|litres?|liters?|kg)\b",
            re.IGNORECASE,
        ),
    ),
    (
        "dose_rate",
        re.compile(
            r"\b\d+(?:\.\d+)?\s*(?:ml|litres?|liters?|kg|grams?)\s*(?:per|/)\s*"
            r"(?:litre|liter|square\s+metre|square\s+meter|acre|hectare|ha)\b",
            re.IGNORECASE,
        ),
    ),
    (
        "diagnosis_claim",
        re.compile(
            r"\b(?:confirmed|diagnosed|definite)\s+(?:a\s+)?"
            r"(?:disease|infection|rust|blight|blast|wilt|rot|diagnosis)\b",
            re.IGNORECASE,
        ),
    ),
    (
        "guarantee",
        re.compile(
            r"\b(?:guaranteed?|will definitely|will cure|will prevent|"
            r"100\s*%)|\bcertain\s+to\s+(?:cure|prevent)\b",
            re.IGNORECASE,
        ),
    ),
    (
        "trading",
        re.compile(
            r"\b(?:buy\s+now|sell\s+now|sell\s+your|profit|trading\s+signal|"
            r"price\s+(?:prediction|forecast)|speculat\w+)\b",
            re.IGNORECASE,
        ),
    ),
)

# Words that may sit between a negation and the unsafe phrase.
_NEGATORS = (
    "do not",
    "don't",
    "never",
    "not ",
    "no ",
    "without",
    "cannot",
    "can't",
    "avoid",
    "instead",
    "rather than",
    "refrain",
)

_NEGATION_WINDOW = 32


def find_unsafe(text: str) -> list[str]:
    """Return the unsafe-pattern names found in ``text`` (empty when clean).

    A match preceded by a negation inside the look-back window is allowed, so
    "Do not apply chemicals based only on an image" passes while "Spray
    pesticide ..." is flagged.
    """
    hits: list[str] = []
    for name, pattern in _UNSAFE_PATTERNS:
        for match in pattern.finditer(text):
            prefix = text[max(0, match.start() - _NEGATION_WINDOW) : match.start()].casefold()
            if any(negator in prefix for negator in _NEGATORS):
                continue
            hits.append(name)
            break
    return hits


def contains_unsafe(text: str) -> bool:
    """True when ``text`` contains at least one actionable unsafe phrase."""
    return bool(find_unsafe(text))
