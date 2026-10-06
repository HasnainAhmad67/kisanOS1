"""Shared pytest fixtures.

The suite never makes live outbound requests: the AMIS reader is disabled for
every test unless a test enables it explicitly (``test_market_amis.py`` also
mocks the HTTP call), so ``pytest -q`` stays deterministic and offline whatever
``backend/.env`` says about ``AMIS_ENABLED``.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.core.config import get_settings
from app.team_agents.market import amis as amis_mod


@pytest.fixture(autouse=True)
def _amis_disabled(monkeypatch: pytest.MonkeyPatch):
    settings = get_settings()
    monkeypatch.setattr(
        amis_mod,
        "get_settings",
        lambda: SimpleNamespace(
            amis_enabled=False,
            amis_wheat_url=settings.amis_wheat_url,
            amis_timeout_sec=settings.amis_timeout_sec,
            amis_cache_ttl_sec=settings.amis_cache_ttl_sec,
        ),
    )
    monkeypatch.setattr(amis_mod, "fetch_html", _refuse_live_fetch)
    yield
    amis_mod.clear_cache()


def _refuse_live_fetch(url: str, timeout: float) -> str:  # pragma: no cover - guard
    raise AssertionError(f"live AMIS request attempted during tests: {url}")
