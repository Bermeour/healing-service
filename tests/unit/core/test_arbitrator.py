from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.core.arbitrator import HealingArbitrator
from app.core.exceptions import BaselineNotFound, HealingFailed
from app.engines.base import ElementBaseline, EngineResult


def _make_request(selector="//button[@id='x']", project="test"):
    req = MagicMock()
    req.selector_value = selector
    req.project = project
    req.test_id = "test_001"
    req.dom_html = "<html><body><button>X</button></body></html>"
    req.screenshot_base64 = None
    return req


def _make_baseline():
    return ElementBaseline(
        tag="button",
        xpath_original="//button[@id='x']",
        id="x",
        text="X",
        classes=[],
    )


def _make_engine(name: str, result: EngineResult) -> MagicMock:
    engine = MagicMock()
    engine.name = name
    engine.heal = AsyncMock(return_value=result)
    return engine


# ── Tests ─────────────────────────────────────────────────────────────────────

class TestHealingArbitrator:

    @pytest.mark.asyncio
    async def test_returns_first_engine_result_when_found(self):
        dom_result = EngineResult(
            found=True, selector="//button[1]", selector_type="xpath",
            confidence=0.9, strategy="DOM", message="ok"
        )
        dom_engine = _make_engine("DOM", dom_result)
        cv_engine  = _make_engine("CV", EngineResult.failed("CV", "no usado"))

        baseline_repo = AsyncMock()
        baseline_repo.get = AsyncMock(return_value=_make_baseline())
        healing_repo = AsyncMock()
        healing_repo.save = AsyncMock()

        arb = HealingArbitrator([dom_engine, cv_engine], baseline_repo, healing_repo)
        result = await arb.heal(_make_request())

        assert result.found
        assert result.strategy == "DOM"
        cv_engine.heal.assert_not_called()  # CV no debe intentarse si DOM resuelve
        healing_repo.save.assert_called_once()

    @pytest.mark.asyncio
    async def test_falls_through_to_cv_when_dom_fails(self):
        dom_result = EngineResult.failed("DOM", "score bajo", confidence=0.3)
        cv_result  = EngineResult(
            found=True, selector="coords::100,200", selector_type="coords",
            confidence=0.91, strategy="CV", message="ok"
        )
        dom_engine = _make_engine("DOM", dom_result)
        cv_engine  = _make_engine("CV", cv_result)

        baseline_repo = AsyncMock()
        baseline_repo.get = AsyncMock(return_value=_make_baseline())
        healing_repo = AsyncMock()
        healing_repo.save = AsyncMock()

        arb = HealingArbitrator([dom_engine, cv_engine], baseline_repo, healing_repo)
        result = await arb.heal(_make_request())

        assert result.found
        assert result.strategy == "CV"
        dom_engine.heal.assert_called_once()
        cv_engine.heal.assert_called_once()

    @pytest.mark.asyncio
    async def test_raises_baseline_not_found_when_no_baseline(self):
        baseline_repo = AsyncMock()
        baseline_repo.get = AsyncMock(return_value=None)
        healing_repo = AsyncMock()

        arb = HealingArbitrator([], baseline_repo, healing_repo)

        with pytest.raises(BaselineNotFound):
            await arb.heal(_make_request())

    @pytest.mark.asyncio
    async def test_raises_healing_failed_when_all_engines_fail(self):
        dom_result = EngineResult.failed("DOM", "score bajo", confidence=0.2)
        cv_result  = EngineResult.failed("CV",  "conf baja",  confidence=0.4)

        dom_engine = _make_engine("DOM", dom_result)
        cv_engine  = _make_engine("CV",  cv_result)

        baseline_repo = AsyncMock()
        baseline_repo.get = AsyncMock(return_value=_make_baseline())
        healing_repo = AsyncMock()

        arb = HealingArbitrator([dom_engine, cv_engine], baseline_repo, healing_repo)

        with pytest.raises(HealingFailed) as exc_info:
            await arb.heal(_make_request())

        assert "DOM" in str(exc_info.value) or "CV" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_register_baseline_delegates_to_repo(self):
        baseline_repo = AsyncMock()
        baseline_repo.save = AsyncMock()
        healing_repo = AsyncMock()

        arb = HealingArbitrator([], baseline_repo, healing_repo)
        req = _make_request()
        await arb.register_baseline(req)

        baseline_repo.save.assert_called_once_with(req)
