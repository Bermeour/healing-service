from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from app.core.cache import get_cache
from app.core.config import settings
from app.core.exceptions import AmbiguousMatch, BaselineNotFound, HealingFailed
from app.engines.dom.selector_validator import selector_exists

from app.engines.base import EngineResult

if TYPE_CHECKING:
    from app.engines.base import HealingEngine
    from app.storage.repositories.baseline_repo import BaselineRepository
    from app.storage.repositories.healing_repo import HealingRepository
    from app.storage.repositories.weights_repo import WeightsRepository

log = logging.getLogger("healing.arbitrator")


class HealingArbitrator:
    """
    Orquesta los motores de self-healing en orden de prioridad.
    El primero en encontrar un candidato válido gana.
    """

    def __init__(
        self,
        engines: list[HealingEngine],
        baseline_repo: BaselineRepository,
        healing_repo: HealingRepository,
        weights_repo: WeightsRepository | None = None,
    ) -> None:
        self._engines = engines
        self._baseline_repo = baseline_repo
        self._healing_repo = healing_repo
        self._weights_repo = weights_repo

    async def heal(self, request) -> EngineResult:
        cache = get_cache()

        # ── Caché ────────────────────────────────────────────────────────────
        cached = cache.get(request.project, request.selector_value)
        if cached is not None:
            log.info(
                "Cache hit | project=%s selector=%.60s confianza=%.2f",
                request.project, request.selector_value, cached.confidence,
            )
            cached._from_cache = True
            return cached

        # ── Baseline ─────────────────────────────────────────────────────────
        baseline = await self._baseline_repo.get(
            selector=request.selector_value,
            project=request.project,
        )
        if baseline is None:
            raise BaselineNotFound(request.selector_value, request.project)

        # ── Último selector sanado (validación rápida pre-scoring) ────────────
        # Antes de hacer scoring DOM completo, comprueba si el último selector
        # sanado para este elemento sigue existiendo en el DOM actual.
        # Es mucho más barato que correr el scoring completo.
        last = await self._healing_repo.get_last_healed_selector(
            original_selector=request.selector_value,
            project=request.project,
        )
        if last:
            last_selector, last_type = last
            if selector_exists(request.dom_html, last_selector, last_type):
                log.info(
                    "Selector histórico válido | project=%s selector=%.60s → %.60s",
                    request.project, request.selector_value, last_selector,
                )
                result = EngineResult(
                    found=True,
                    selector=last_selector,
                    selector_type=last_type,
                    confidence=1.0,
                    strategy="HISTORY",
                    message="Selector previamente sanado sigue siendo válido en el DOM actual",
                )
                saved_event = await self._healing_repo.save(request, result)
                result._event_id = saved_event.id
                cache.set(request.project, request.selector_value, result)
                return result
            else:
                log.debug(
                    "Selector histórico ya no existe en DOM | project=%s → ejecutando motores",
                    request.project,
                )

        # ── Pesos aprendidos ──────────────────────────────────────────────────
        learned_weights = None
        if self._weights_repo:
            record = await self._weights_repo.get(request.project)
            if record:
                learned_weights = record.weights
                log.debug(
                    "Usando pesos aprendidos para project=%s (sample=%d)",
                    request.project, record.sample_size,
                )

        context = {
            "dom_html": request.dom_html,
            "baseline": baseline,
            "screenshot_b64": request.screenshot_base64,
            "scoring_profile": getattr(request, "scoring_profile", "default"),
            "learned_weights": learned_weights,
            # filtros de contexto (opcionales, vacíos por defecto)
            "exclude_ids":     getattr(request, "exclude_ids", []),
            "container_id":    getattr(request, "container_id", None),
            "container_class": getattr(request, "container_class", None),
            "form_id":         getattr(request, "form_id", None),
            "anchors":         getattr(request, "anchors", []),
        }

        last_scores: dict[str, float] = {}

        for engine in self._engines:
            log.debug("Intentando motor: %s", engine.name)

            try:
                result = await engine.heal(context)
            except AmbiguousMatch as exc:
                log.warning("%s — pasando al siguiente motor", exc)
                last_scores[engine.name] = 0.0
                continue

            if result.found:
                log.info(
                    "Sanado por %s | selector=%s | confianza=%.2f",
                    engine.name, result.selector, result.confidence,
                )
                saved_event = await self._healing_repo.save(request, result)
                result._event_id = saved_event.id

                # ── Caché del resultado ───────────────────────────────────────
                cache.set(request.project, request.selector_value, result)

                # ── Auto-update de baseline (alta confianza) ──────────────────
                if (
                    settings.auto_update_baseline
                    and result.confidence >= settings.auto_update_baseline_threshold
                    and result.selector_type == "xpath"
                ):
                    await self._try_auto_update_baseline(
                        request=request,
                        new_selector=result.selector,
                        context=context,
                    )

                return result

            last_scores[engine.name] = result.confidence
            log.debug(
                "Motor %s no encontró candidato válido (confianza=%.2f)",
                engine.name, result.confidence,
            )

        dom_score = last_scores.get("DOM", 0.0)
        cv_conf = last_scores.get("CV", 0.0)
        raise HealingFailed(request.selector_value, dom_score, cv_conf)

    async def _try_auto_update_baseline(
        self,
        request,
        new_selector: str,
        context: dict,
    ) -> None:
        """
        Actualiza el baseline al nuevo selector cuando la confianza es muy alta.
        Extrae los metadatos del nuevo nodo desde el DOM actual.
        """
        try:
            from app.engines.dom.extractor import parse_dom
            from app.engines.base import ElementBaseline

            baseline: ElementBaseline = context["baseline"]
            _, candidates = parse_dom(request.dom_html, baseline.tag)

            # Busca el candidato que generó el new_selector
            # Comparamos reconstruyendo el xpath — buscamos el nodo más probable
            # (el de mayor score ya fue seleccionado, lo identificamos por xpath)
            from app.engines.dom.xpath_builder import build_xpath
            matched_meta = None
            for cand in candidates:
                if build_xpath(cand["node"]) == new_selector:
                    matched_meta = cand
                    break

            if matched_meta is None:
                log.debug("Auto-update: no se encontró el nodo exacto en DOM — omitido")
                return

            new_meta = {
                "tag": matched_meta.get("tag", baseline.tag),
                "id": matched_meta.get("id", ""),
                "name": matched_meta.get("name", ""),
                "text": matched_meta.get("text", ""),
                "classes": matched_meta.get("classes", []),
                "aria_label": matched_meta.get("aria_label", ""),
                "placeholder": matched_meta.get("placeholder", ""),
                "parent_tag": matched_meta.get("parent_tag", ""),
                "siblings_count": matched_meta.get("siblings_count", 0),
                "type": matched_meta.get("type", ""),
                "role": matched_meta.get("role", ""),
                "data_testid": matched_meta.get("data_testid", ""),
            }

            updated = await self._baseline_repo.update_from_healing(
                selector=request.selector_value,
                project=request.project,
                new_meta=new_meta,
                new_selector_value=new_selector,
            )

            if updated:
                # Invalida caché — el selector antiguo ya no es válido
                get_cache().invalidate(request.project, request.selector_value)
                log.info(
                    "Baseline auto-actualizado | project=%s selector_viejo=%.60s → selector_nuevo=%.60s",
                    request.project, request.selector_value, new_selector,
                )

        except Exception as exc:
            # El auto-update nunca debe romper el healing principal
            log.warning("Auto-update de baseline falló (no crítico): %s", exc)

    async def register_baseline(self, request) -> None:
        await self._baseline_repo.register(request)
        log.info(
            "Baseline registrado | proyecto=%s | selector=%s",
            request.project,
            request.selector_value,
        )