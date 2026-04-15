from __future__ import annotations

import base64

import pytest
import pytest_asyncio

from app.engines.base import EngineResult
from app.models.baseline import Baseline


# ── BaselineRepository ────────────────────────────────────────────────────────

class TestBaselineRepository:

    @pytest.mark.asyncio
    async def test_returns_none_when_not_found(self, baseline_repo):
        result = await baseline_repo.get("//nonexistent", "proyecto")
        assert result is None

    @pytest.mark.asyncio
    async def test_register_creates_baseline(self, baseline_repo, baseline_request_payload):
        request = _dict_to_request(baseline_request_payload)
        row = await baseline_repo.register(request)

        assert row.id is not None
        assert row.project == "test_project"
        assert row.selector_value == "//button[@id='btn-submit']"
        assert row.tag == "button"
        assert row.heal_count == 0

    @pytest.mark.asyncio
    async def test_register_upserts_existing(self, baseline_repo, baseline_request_payload):
        request = _dict_to_request(baseline_request_payload)
        first  = await baseline_repo.register(request)
        second = await baseline_repo.register(request)

        assert first.id == second.id  # mismo registro, no duplicado

    @pytest.mark.asyncio
    async def test_get_returns_element_baseline(self, baseline_repo, baseline_request_payload):
        request = _dict_to_request(baseline_request_payload)
        await baseline_repo.register(request)

        baseline = await baseline_repo.get("//button[@id='btn-submit']", "test_project")
        assert baseline is not None
        assert baseline.tag == "button"
        assert baseline.id == "btn-submit"
        assert baseline.text == "Iniciar sesión"
        assert "btn-primary" in baseline.classes

    @pytest.mark.asyncio
    async def test_list_by_project_returns_all(self, baseline_repo, baseline_request_payload):
        req1 = _dict_to_request(baseline_request_payload)
        req2 = _dict_to_request({
            **baseline_request_payload,
            "selector_value": "//input[@id='username']",
            "element_meta": {**baseline_request_payload["element_meta"], "tag": "input", "id": "username"},
        })
        await baseline_repo.register(req1)
        await baseline_repo.register(req2)

        rows = await baseline_repo.list_by_project("test_project")
        selectors = [r.selector_value for r in rows]
        assert "//button[@id='btn-submit']" in selectors
        assert "//input[@id='username']" in selectors

    @pytest.mark.asyncio
    async def test_increment_heal_count(self, baseline_repo, baseline_request_payload):
        request = _dict_to_request(baseline_request_payload)
        await baseline_repo.register(request)

        await baseline_repo.increment_heal_count("//button[@id='btn-submit']", "test_project")
        row = await baseline_repo.get_orm("//button[@id='btn-submit']", "test_project")
        assert row.heal_count == 1


# ── HealingRepository ─────────────────────────────────────────────────────────

class TestHealingRepository:

    @pytest.mark.asyncio
    async def test_get_stats_empty_project(self, healing_repo):
        stats = await healing_repo.get_stats("proyecto_sin_datos")
        assert stats["total_healings"] == 0
        assert stats["by_strategy"]["DOM"] == 0
        assert stats["by_strategy"]["CV"] == 0

    @pytest.mark.asyncio
    async def test_get_history_empty(self, healing_repo):
        events = await healing_repo.get_history("proyecto_sin_datos")
        assert events == []

    @pytest.mark.asyncio
    async def test_save_records_event(self, baseline_repo, healing_repo, baseline_request_payload):
        # Registra el baseline primero
        request = _dict_to_request(baseline_request_payload)
        await baseline_repo.register(request)

        result = EngineResult(
            found=True,
            selector="//button[1]",
            selector_type="xpath",
            confidence=0.85,
            strategy="DOM",
            message="Sanado",
        )
        await healing_repo.save(request, result)

        events = await healing_repo.get_history("test_project")
        assert len(events) == 1
        assert events[0].strategy == "DOM"
        assert events[0].confidence == pytest.approx(0.85)
        assert events[0].healed_selector == "//button[1]"

    @pytest.mark.asyncio
    async def test_get_stats_after_healings(self, baseline_repo, healing_repo, baseline_request_payload):
        request = _dict_to_request(baseline_request_payload)
        await baseline_repo.register(request)

        dom_result = EngineResult(True, "//x", "xpath", 0.9, "DOM", "")
        cv_result  = EngineResult(True, "coords::1,2", "coords", 0.88, "CV", "")

        await healing_repo.save(request, dom_result)
        await healing_repo.save(request, cv_result)

        stats = await healing_repo.get_stats("test_project")
        assert stats["total_healings"] == 2
        assert stats["by_strategy"]["DOM"] == 1
        assert stats["by_strategy"]["CV"] == 1


# ── helpers ───────────────────────────────────────────────────────────────────

def _dict_to_request(payload: dict):
    from unittest.mock import MagicMock
    req = MagicMock()
    req.selector_type   = payload["selector_type"]
    req.selector_value  = payload["selector_value"]
    req.screenshot_base64 = payload.get("screenshot_base64", "")
    req.element_meta    = payload["element_meta"]
    req.test_id         = payload.get("test_id", "test")
    req.project         = payload.get("project", "test_project")
    return req
