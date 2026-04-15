from __future__ import annotations

import logging
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.engines.base import EngineResult
from app.models.baseline import Baseline
from app.models.healing_event import HealingEvent
from app.storage.repositories.base_repo import BaseRepository

log = logging.getLogger("healing.storage.healing")


class HealingRepository(BaseRepository[HealingEvent]):

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, HealingEvent)

    async def save(self, request, result: EngineResult) -> HealingEvent:
        """Registra una sanación exitosa y actualiza el heal_count del baseline."""
        baseline_id = await self._get_baseline_id(request.selector_value, request.project)

        event = HealingEvent(
            baseline_id=baseline_id,
            project=request.project,
            test_id=request.test_id,
            original_selector=request.selector_value,
            healed_selector=result.selector,
            selector_type=result.selector_type,
            strategy=result.strategy,
            confidence=result.confidence,
        )
        self._session.add(event)   # primero agregar al contexto de sesión

        # Actualiza contador en el baseline
        if baseline_id:
            bl = await self._session.get(Baseline, baseline_id)
            if bl:
                bl.heal_count += 1

        await self._session.flush()   # luego flush para persistir ambos cambios
        log.debug(
            "Evento guardado: project=%s test=%s strategy=%s conf=%.2f",
            request.project, request.test_id, result.strategy, result.confidence,
        )
        return event

    async def get_history(
        self,
        project: str,
        test_id: str | None = None,
        limit: int = 50,
    ) -> list[HealingEvent]:
        """Historial de sanaciones filtrado por proyecto y opcionalmente por test."""
        stmt = (
            select(HealingEvent)
            .where(HealingEvent.project == project)
            .order_by(HealingEvent.healed_at.desc())
            .limit(limit)
        )
        if test_id:
            stmt = stmt.where(HealingEvent.test_id == test_id)

        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def get_stats(self, project: str) -> dict:
        """Estadísticas agregadas para el endpoint /metrics."""
        total_stmt = select(func.count()).where(HealingEvent.project == project)
        dom_stmt = select(func.count()).where(
            HealingEvent.project == project,
            HealingEvent.strategy == "DOM",
        )
        cv_stmt = select(func.count()).where(
            HealingEvent.project == project,
            HealingEvent.strategy == "CV",
        )
        history_stmt = select(func.count()).where(
            HealingEvent.project == project,
            HealingEvent.strategy == "HISTORY",
        )
        avg_conf_stmt = select(func.avg(HealingEvent.confidence)).where(
            HealingEvent.project == project,
        )

        total = (await self._session.execute(total_stmt)).scalar_one()
        dom = (await self._session.execute(dom_stmt)).scalar_one()
        cv = (await self._session.execute(cv_stmt)).scalar_one()
        history = (await self._session.execute(history_stmt)).scalar_one()
        avg_conf = (await self._session.execute(avg_conf_stmt)).scalar_one() or 0.0

        return {
            "project": project,
            "total_healings": total,
            "by_strategy": {"DOM": dom, "CV": cv, "HISTORY": history},
            "avg_confidence": round(float(avg_conf), 3),
        }

    async def get_last_healed_selector(
        self,
        original_selector: str,
        project: str,
    ) -> tuple[str, str] | None:
        """
        Devuelve el último selector sanado exitoso para este elemento.

        Prioriza eventos con feedback_correct=True (confirmados por el cliente).
        Si no hay feedback explícito, devuelve el más reciente con alta confianza.

        Returns:
            (healed_selector, selector_type) o None si no hay historial.
        """
        # Primero: busca el último con feedback positivo confirmado
        confirmed_stmt = (
            select(HealingEvent.healed_selector, HealingEvent.selector_type)
            .where(
                HealingEvent.project == project,
                HealingEvent.original_selector == original_selector,
                HealingEvent.feedback_correct == True,   # noqa: E712
                HealingEvent.selector_type != "coords",  # coords no son validables en DOM
            )
            .order_by(HealingEvent.healed_at.desc())
            .limit(1)
        )
        row = (await self._session.execute(confirmed_stmt)).first()
        if row:
            log.debug(
                "Último selector confirmado encontrado | project=%s selector=%.60s",
                project, original_selector,
            )
            return row[0], row[1]

        # Fallback: más reciente de alta confianza sin feedback negativo explícito
        recent_stmt = (
            select(HealingEvent.healed_selector, HealingEvent.selector_type)
            .where(
                HealingEvent.project == project,
                HealingEvent.original_selector == original_selector,
                HealingEvent.confidence >= 0.85,
                HealingEvent.feedback_correct.is_not(False),  # excluye los confirmados incorrectos
                HealingEvent.selector_type != "coords",
            )
            .order_by(HealingEvent.healed_at.desc())
            .limit(1)
        )
        row = (await self._session.execute(recent_stmt)).first()
        if row:
            log.debug(
                "Último selector reciente de alta confianza | project=%s selector=%.60s",
                project, original_selector,
            )
            return row[0], row[1]

        return None

    async def get_event(self, event_id: int) -> HealingEvent | None:
        return await self._session.get(HealingEvent, event_id)

    async def save_feedback(
        self,
        event_id: int,
        correct: bool,
        confirmed_selector: str | None = None,
    ) -> HealingEvent | None:
        """
        Registra el feedback del cliente sobre si el healing fue correcto.

        Args:
            event_id: ID del evento de sanación
            correct: True si el selector encontrado funcionó realmente
            confirmed_selector: Selector que el cliente confirmó como correcto (opcional)

        Returns:
            El evento actualizado, o None si no existe.
        """
        event = await self.get_event(event_id)
        if event is None:
            log.warning("Feedback para evento inexistente: id=%d", event_id)
            return None

        event.feedback_correct = correct
        event.confirmed_selector = confirmed_selector
        event.feedback_at = datetime.now(timezone.utc)
        await self._session.flush()

        log.info(
            "Feedback registrado | event_id=%d correct=%s project=%s",
            event_id, correct, event.project,
        )
        return event

    async def _get_baseline_id(self, selector: str, project: str) -> int | None:
        result = await self._session.execute(
            select(Baseline.id).where(
                Baseline.project == project,
                Baseline.selector_value == selector,
            )
        )
        return result.scalar_one_or_none()
