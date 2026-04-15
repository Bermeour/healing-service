from __future__ import annotations

import pytest

from app.engines.base import ElementBaseline
from app.engines.dom.extractor import parse_dom
from app.engines.dom.scorer import THRESHOLD, score_candidate
from app.engines.dom.xpath_builder import build_xpath
from app.engines.dom.engine import DOMEngine
from app.core.exceptions import AmbiguousMatch


# ── score_candidate ───────────────────────────────────────────────────────────

class TestScoreCandidate:

    def test_exact_id_match_scores_high(self, sample_baseline):
        candidate = {"tag": "button", "id": "btn-submit", "name": "", "text": "",
                     "classes": [], "aria_label": "", "placeholder": "",
                     "parent_tag": "", "siblings_count": 0, "type": "", "role": "",
                     "data_testid": ""}
        score = score_candidate(sample_baseline, candidate)
        assert score >= 40  # solo id ya supera umbral mínimo

    def test_text_and_classes_match(self, sample_baseline):
        candidate = {"tag": "button", "id": "", "name": "", "text": "Iniciar sesión",
                     "classes": ["btn", "btn-primary"], "aria_label": "", "placeholder": "",
                     "parent_tag": "form", "siblings_count": 1, "type": "submit", "role": "",
                     "data_testid": ""}
        score = score_candidate(sample_baseline, candidate)
        assert score >= THRESHOLD

    def test_data_testid_scores_highest(self):
        baseline = ElementBaseline(
            tag="button", xpath_original="//button",
            id="", text="", classes=[]
        )
        # Simula que el baseline también tiene data_testid
        baseline.__dict__["data_testid"] = "btn-login"

        candidate = {"tag": "button", "id": "", "name": "", "text": "",
                     "classes": [], "aria_label": "", "placeholder": "",
                     "parent_tag": "", "siblings_count": 0, "type": "", "role": "",
                     "data_testid": "btn-login"}
        score = score_candidate(baseline, candidate)
        assert score >= 50

    def test_no_match_scores_zero(self, sample_baseline):
        candidate = {"tag": "button", "id": "otro-btn", "name": "otro",
                     "text": "Cerrar", "classes": ["btn-danger"],
                     "aria_label": "", "placeholder": "", "parent_tag": "div",
                     "siblings_count": 5, "type": "", "role": "", "data_testid": ""}
        score = score_candidate(sample_baseline, candidate)
        assert score < THRESHOLD

    def test_partial_text_scores_less_than_exact(self, sample_baseline):
        exact = {"tag": "button", "id": "", "name": "", "text": "Iniciar sesión",
                 "classes": [], "aria_label": "", "placeholder": "",
                 "parent_tag": "", "siblings_count": 0, "type": "", "role": "",
                 "data_testid": ""}
        partial = {"tag": "button", "id": "", "name": "", "text": "Iniciar sesión ahora",
                   "classes": [], "aria_label": "", "placeholder": "",
                   "parent_tag": "", "siblings_count": 0, "type": "", "role": "",
                   "data_testid": ""}
        assert score_candidate(sample_baseline, exact) > score_candidate(sample_baseline, partial)


# ── parse_dom ─────────────────────────────────────────────────────────────────

class TestDOMExtractor:

    def test_extracts_correct_tag(self, sample_dom):
        candidates = parse_dom(sample_dom, "button")
        assert len(candidates) == 2
        assert all(c["tag"] == "button" for c in candidates)

    def test_extracts_id(self, sample_dom):
        candidates = parse_dom(sample_dom, "button")
        ids = [c["id"] for c in candidates]
        assert "btn-submit" in ids

    def test_extracts_classes(self, sample_dom):
        candidates = parse_dom(sample_dom, "button")
        submit = next(c for c in candidates if c["id"] == "btn-submit")
        assert "btn-primary" in submit["classes"]

    def test_empty_dom_returns_empty(self):
        assert parse_dom("", "button") == []

    def test_tag_not_present_returns_empty(self, sample_dom):
        assert parse_dom(sample_dom, "select") == []


# ── xpath_builder ─────────────────────────────────────────────────────────────

class TestXPathBuilder:

    def test_builds_absolute_xpath(self, sample_dom):
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(sample_dom, "lxml")
        button = soup.find("button", {"id": "btn-submit"})
        xpath = build_xpath(button)
        assert xpath.startswith("/")
        assert "button" in xpath

    def test_xpath_uses_stable_attr_over_index(self, sample_dom):
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(sample_dom, "lxml")
        button = soup.find("button", {"id": "btn-cancel"})
        xpath = build_xpath(button)
        # Con id disponible, el builder debe preferir atributo estable en lugar de índice posicional
        assert "@id='btn-cancel'" in xpath or "btn-cancel" in xpath


# ── DOMEngine ─────────────────────────────────────────────────────────────────

class TestDOMEngine:

    @pytest.mark.asyncio
    async def test_heals_changed_id(self, sample_baseline, changed_dom):
        engine = DOMEngine(threshold=THRESHOLD)
        context = {"dom_html": changed_dom, "baseline": sample_baseline, "screenshot_b64": None}
        result = await engine.heal(context)
        assert result.found
        assert result.strategy == "DOM"
        assert result.selector.startswith("/")
        assert result.confidence > 0

    @pytest.mark.asyncio
    async def test_fails_when_element_absent(self, sample_baseline):
        empty_dom = "<html><body><div>sin botones</div></body></html>"
        engine = DOMEngine(threshold=THRESHOLD)
        context = {"dom_html": empty_dom, "baseline": sample_baseline, "screenshot_b64": None}
        result = await engine.heal(context)
        assert not result.found
        assert result.strategy == "DOM"

    @pytest.mark.asyncio
    async def test_raises_ambiguous_on_tie(self):
        """Dos botones idénticos deben lanzar AmbiguousMatch."""
        baseline = ElementBaseline(
            tag="button", xpath_original="//button",
            text="OK", classes=["btn"],
        )
        twin_dom = """
        <html><body>
          <button class="btn">OK</button>
          <button class="btn">OK</button>
        </body></html>
        """
        engine = DOMEngine(threshold=10)  # umbral bajo para que ambos califiquen
        context = {"dom_html": twin_dom, "baseline": baseline, "screenshot_b64": None}
        with pytest.raises(AmbiguousMatch):
            await engine.heal(context)

    @pytest.mark.asyncio
    async def test_capture_baseline_returns_element_baseline(self):
        engine = DOMEngine()
        context = {
            "element_meta": {
                "tag": "input", "id": "user", "name": "username",
                "text": "", "classes": ["form-control"], "aria_label": "",
                "placeholder": "Usuario", "parent_tag": "div", "siblings_count": 0,
            },
            "xpath_original": "//input[@id='user']",
        }
        baseline = await engine.capture_baseline(context)
        assert baseline.tag == "input"
        assert baseline.id == "user"
        assert baseline.placeholder == "Usuario"
