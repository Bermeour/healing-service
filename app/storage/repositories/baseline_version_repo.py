from __future__ import annotations

import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.baseline import Baseline
from app.models.baseline_version import BaselineVersion

log = logging.getLogger("healing.storage.baseline_version")


class BaselineVersionRepository:

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def snapshot(self, baseline: Baseline, reason: str = "manual") -> BaselineVersion:
        """
        Guarda una copia del estado actual del baseline antes de que sea modificado.
        Asigna version_number incremental dentro del mismo baseline.
        """
        next_version = await self._next_version_number(baseline.id)

        version = BaselineVersion(
            baseline_id=baseline.id,
            project=baseline.project,
            selector_value=baseline.selector_value,
            selector_type=baseline.selector_type,
            tag=baseline.tag,
            element_meta=dict(baseline.element_meta or {}),
            visual_snapshot_path=baseline.visual_snapshot_path or "",
            version_number=next_version,
            reason=reason,
        )
        self._session.add(version)
        await self._session.flush()

        log.info(
            "Versión %d guardada para baseline_id=%d project=%s selector=%.60s reason=%s",
            next_version, baseline.id, baseline.project, baseline.selector_value, reason,
        )
        return version

    async def list_versions(self, project: str, selector: str) -> list[BaselineVersion]:
        """Devuelve todas las versiones históricas de un selector, orden descendente."""
        result = await self._session.execute(
            select(BaselineVersion)
            .where(
                BaselineVersion.project == project,
                BaselineVersion.selector_value == selector,
            )
            .order_by(BaselineVersion.version_number.desc())
        )
        return list(result.scalars().all())

    async def get_version(self, version_id: int) -> BaselineVersion | None:
        return await self._session.get(BaselineVersion, version_id)

    async def _next_version_number(self, baseline_id: int) -> int:
        from sqlalchemy import func
        result = await self._session.execute(
            select(func.max(BaselineVersion.version_number)).where(
                BaselineVersion.baseline_id == baseline_id
            )
        )
        current_max = result.scalar_one_or_none()
        return (current_max or 0) + 1
