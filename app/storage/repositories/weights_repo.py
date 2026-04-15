from __future__ import annotations

import logging
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.engines.dom.weight_learner import learn_weights
from app.models.baseline import Baseline
from app.models.healing_event import HealingEvent
from app.models.learned_weights import LearnedWeights

log = logging.getLogger("healing.storage.weights")


class WeightsRepository:

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get(self, project: str) -> LearnedWeights | None:
        """Devuelve los pesos aprendidos para un proyecto, o None si no existen."""
        result = await self._session.execute(
            select(LearnedWeights).where(LearnedWeights.project == project)
        )
        return result.scalar_one_or_none()

    async def run_learning(self, project: str, base_profile: str = "default") -> dict:
        """
        Ejecuta el ciclo de aprendizaje completo para un proyecto:
          1. Consulta todos los eventos DOM exitosos con sus metadatos de baseline.
          2. Calcula los nuevos pesos con el algoritmo de lift por atributo.
          3. Guarda (upsert) los pesos en la tabla learned_weights.

        Devuelve el dict de estadísticas generado por weight_learner.
        """
        events = await self._fetch_events(project)
        learned, stats = learn_weights(events, base_profile)

        if not stats.get("skipped"):
            await self._upsert(project, learned, len(events), stats["global_mean_confidence"])
            log.info(
                "Pesos guardados para project=%s (sample=%d)",
                project, len(events),
            )

        return stats

    async def _fetch_events(self, project: str) -> list[dict]:
        """
        Devuelve los eventos DOM exitosos del proyecto con el element_meta
        de su baseline — la materia prima para el aprendizaje.
        """
        stmt = (
            select(HealingEvent.confidence, Baseline.element_meta)
            .join(Baseline, HealingEvent.baseline_id == Baseline.id)
            .where(
                HealingEvent.project == project,
                HealingEvent.strategy == "DOM",
            )
        )
        rows = await self._session.execute(stmt)
        return [
            {"confidence": float(conf), "element_meta": meta or {}}
            for conf, meta in rows.all()
        ]

    async def _upsert(
        self,
        project: str,
        weights: dict,
        sample_size: int,
        avg_confidence: float,
    ) -> None:
        """Crea o actualiza el registro de pesos aprendidos para el proyecto."""
        existing = await self.get(project)

        if existing:
            existing.weights = weights
            existing.sample_size = sample_size
            existing.avg_confidence = avg_confidence
            existing.learned_at = datetime.now(timezone.utc)
        else:
            self._session.add(LearnedWeights(
                project=project,
                weights=weights,
                sample_size=sample_size,
                avg_confidence=avg_confidence,
            ))

        await self._session.flush()
