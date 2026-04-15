from __future__ import annotations

import logging

from app.core.exceptions import AmbiguousMatch
from app.engines.base import ElementBaseline, EngineResult, HealingEngine
from app.engines.dom.anchors import AnchorResolver
from app.engines.dom.extractor import parse_dom
from app.engines.dom.filters import CandidateFilter
from app.engines.dom.scorer import THRESHOLD, WEIGHT_PROFILES, score_candidate
from app.engines.dom.xpath_builder import build_xpath

log = logging.getLogger("healing.engine.dom")

_anchor_resolver = AnchorResolver()
_candidate_filter = CandidateFilter()


class DOMEngine(HealingEngine):
    """
    Motor de self-healing basado en scoring de atributos del DOM.

    Estrategia:
    1. Extrae todos los nodos del mismo tag que el elemento buscado.
    2. Aplica filtros duros de contexto (formId, containerId, excludeIds).
    3. Resuelve anchors de referencia para bonus de proximidad DOM.
    4. Puntúa cada candidato contra la huella (baseline) guardada.
    5. Si hay un único ganador sobre el umbral, devuelve su XPath.
    6. Si hay empate en el primer lugar, escala (AmbiguousMatch → CV).
    """

    def __init__(self, threshold: int = THRESHOLD) -> None:
        self._threshold = threshold

    @property
    def name(self) -> str:
        return "DOM"

    async def heal(self, context: dict) -> EngineResult:
        baseline: ElementBaseline = context["baseline"]
        dom_html: str = context["dom_html"]
        profile_name: str = context.get("scoring_profile", "default")
        weights = WEIGHT_PROFILES.get(profile_name, WEIGHT_PROFILES["default"])

        if profile_name not in WEIGHT_PROFILES:
            log.warning(
                "Perfil de scoring desconocido: '%s', usando 'default'", profile_name
            )

        log.debug("Scoring profile: %s", profile_name)

        # Pesos aprendidos tienen prioridad sobre el perfil — si existen
        learned = context.get("learned_weights")
        if learned:
            weights = learned
            log.debug("Scoring con pesos aprendidos para este proyecto")

        soup, candidates = parse_dom(dom_html, baseline.tag)
        if not candidates:
            log.debug("No se encontraron nodos <%s> en el DOM", baseline.tag)
            return EngineResult.failed("DOM", f"No hay nodos <{baseline.tag}> en el DOM")

        # Filtros duros de contexto
        exclude_ids: list[str] = context.get("exclude_ids", [])
        container_id: str | None = context.get("container_id")
        container_class: str | None = context.get("container_class")
        form_id: str | None = context.get("form_id")

        if any([exclude_ids, container_id, container_class, form_id]):
            candidates = [
                c for c in candidates
                if _candidate_filter.accept(
                    c,
                    exclude_ids=exclude_ids,
                    container_id=container_id,
                    container_class=container_class,
                    form_id=form_id,
                )
            ]
            log.debug("Candidatos tras filtros de contexto: %d", len(candidates))
            if not candidates:
                return EngineResult.failed("DOM", "Ningún candidato pasó los filtros de contexto")

        # Anchors: referencias de proximidad DOM
        custom_anchors: list[dict] = context.get("anchors", [])
        anchors = _anchor_resolver.resolve(soup, baseline.text, custom_anchors)
        log.debug("Anchors resueltos: %d", len(anchors))

        scored = []
        for c in candidates:
            base_score = score_candidate(baseline, c, weights)
            anchor_bonus = 0
            if anchors:
                node = c.get("node")
                if node is not None:
                    anchor_bonus = _anchor_resolver.score_for_candidate(node, anchors)
            scored.append((base_score + anchor_bonus, c))

        scored.sort(key=lambda x: x[0], reverse=True)

        best_score, best_candidate = scored[0]
        log.debug("Mejor score DOM: %d (umbral=%d)", best_score, self._threshold)

        if best_score < self._threshold:
            return EngineResult.failed(
                "DOM",
                f"Score máximo {best_score} < umbral {self._threshold}",
                confidence=best_score / 100,
            )

        # Detecta empate en el primer puesto — no es confiable
        top_tied = [s for s, _ in scored if s == best_score]
        if len(top_tied) > 1:
            log.warning(
                "Empate DOM: %d candidatos con score=%d, escalando a CV",
                len(top_tied),
                best_score,
            )
            raise AmbiguousMatch("DOM", len(top_tied), best_score)

        new_xpath = build_xpath(best_candidate["node"])
        log.debug("XPath generado: %s", new_xpath)

        return EngineResult(
            found=True,
            selector=new_xpath,
            selector_type="xpath",
            confidence=round(best_score / 100, 2),
            strategy="DOM",
            message=f"Sanado por DOM Scoring (score={best_score})",
        )

    async def capture_baseline(self, context: dict) -> ElementBaseline:
        meta: dict = context["element_meta"]
        return ElementBaseline(
            tag=meta.get("tag", ""),
            xpath_original=context.get("xpath_original", ""),
            id=meta.get("id", ""),
            name=meta.get("name", ""),
            text=meta.get("text", ""),
            classes=meta.get("classes", []),
            aria_label=meta.get("aria_label", ""),
            placeholder=meta.get("placeholder", ""),
            parent_tag=meta.get("parent_tag", ""),
            siblings_count=meta.get("siblings_count", 0),
            data_cy=meta.get("data_cy", ""),
            data_qa=meta.get("data_qa", ""),
            formcontrolname=meta.get("formcontrolname", ""),
            title=meta.get("title", ""),
            data_display=meta.get("data_display", ""),
        )
