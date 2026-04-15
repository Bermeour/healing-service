from __future__ import annotations

import base64
import logging
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.engines.base import ElementBaseline
from app.models.baseline import Baseline
from app.storage.repositories.base_repo import BaseRepository
from app.storage.repositories.baseline_version_repo import BaselineVersionRepository

log = logging.getLogger("healing.storage.baseline")


class BaselineRepository(BaseRepository[Baseline]):

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, Baseline)

    async def get(self, selector: str, project: str) -> ElementBaseline | None:
        """Devuelve el ElementBaseline activo para un selector en un proyecto."""
        result = await self._session.execute(
            select(Baseline).where(
                Baseline.project == project,
                Baseline.selector_value == selector,
            )
        )
        row = result.scalar_one_or_none()
        if row is None:
            return None
        return row.to_element_baseline()

    async def get_orm(self, selector: str, project: str) -> Baseline | None:
        """Devuelve el modelo ORM completo (para updates internos)."""
        result = await self._session.execute(
            select(Baseline).where(
                Baseline.project == project,
                Baseline.selector_value == selector,
            )
        )
        return result.scalar_one_or_none()

    async def register(self, request) -> Baseline:
        """
        Crea o actualiza el baseline para un selector.
        Si ya existe, guarda la versión anterior antes de sobreescribir.
        """
        existing = await self.get_orm(request.selector_value, request.project)

        snapshot_path = self._save_snapshot(
            screenshot_b64=request.screenshot_base64,
            project=request.project,
            selector=request.selector_value,
        )

        # element_meta puede ser un Pydantic model (desde API) o un dict (desde tests)
        meta = (
            request.element_meta.model_dump()
            if hasattr(request.element_meta, "model_dump")
            else dict(request.element_meta)
        )

        if existing:
            # Guarda snapshot histórico antes de actualizar
            version_repo = BaselineVersionRepository(self._session)
            await version_repo.snapshot(existing, reason="manual")

            existing.selector_type = request.selector_type
            existing.tag = meta.get("tag", existing.tag)
            existing.element_meta = meta
            existing.visual_snapshot_path = snapshot_path
            existing.updated_at = datetime.now(timezone.utc)
            await self._session.flush()
            log.info("Baseline actualizado: project=%s selector=%s", request.project, request.selector_value)
            return existing

        baseline = Baseline(
            project=request.project,
            selector_type=request.selector_type,
            selector_value=request.selector_value,
            tag=meta.get("tag", ""),
            element_meta=meta,
            visual_snapshot_path=snapshot_path,
        )
        await self.save(baseline)
        log.info("Baseline registrado: project=%s selector=%s", request.project, request.selector_value)
        return baseline

    async def update_from_healing(
        self,
        selector: str,
        project: str,
        new_meta: dict,
        new_selector_value: str,
    ) -> bool:
        """
        Actualiza el baseline automáticamente tras una sanación de alta confianza.
        Guarda versión histórica antes de actualizar.
        Devuelve True si el baseline existía y fue actualizado.
        """
        existing = await self.get_orm(selector, project)
        if existing is None:
            return False

        version_repo = BaselineVersionRepository(self._session)
        await version_repo.snapshot(existing, reason="auto_update")

        existing.element_meta = {**existing.element_meta, **new_meta}
        existing.selector_value = new_selector_value
        existing.tag = new_meta.get("tag", existing.tag)
        existing.updated_at = datetime.now(timezone.utc)
        await self._session.flush()

        log.info(
            "Baseline auto-actualizado tras sanación: project=%s selector=%.60s → %.60s",
            project, selector, new_selector_value,
        )
        return True

    async def rollback_to_version(self, version_id: int) -> Baseline | None:
        """
        Restaura el baseline al estado de una versión histórica.
        Guarda el estado actual como versión antes de restaurar.
        Devuelve el baseline actualizado o None si no encontró la versión.
        """
        version_repo = BaselineVersionRepository(self._session)
        version = await version_repo.get_version(version_id)
        if version is None:
            return None

        existing = await self.get_orm(version.selector_value, version.project)
        if existing is None:
            return None

        # Guarda estado actual antes de restaurar
        await version_repo.snapshot(existing, reason="manual")

        existing.element_meta = dict(version.element_meta or {})
        existing.tag = version.tag
        existing.selector_type = version.selector_type
        existing.visual_snapshot_path = version.visual_snapshot_path
        existing.updated_at = datetime.now(timezone.utc)
        await self._session.flush()

        log.info(
            "Baseline restaurado a versión %d | project=%s selector=%.60s",
            version.version_number, version.project, version.selector_value,
        )
        return existing

    async def increment_heal_count(self, selector: str, project: str) -> None:
        row = await self.get_orm(selector, project)
        if row:
            row.heal_count += 1
            await self._session.flush()

    async def list_by_project(self, project: str) -> list[Baseline]:
        result = await self._session.execute(
            select(Baseline).where(Baseline.project == project).order_by(Baseline.created_at)
        )
        return list(result.scalars().all())

    def _save_snapshot(self, screenshot_b64: str, project: str, selector: str) -> str:
        """
        Guarda el recorte visual del elemento en disco.
        Devuelve ruta RELATIVA a baselines_path (ej: "healing_demo/3056...432.png").
        Guardar relativa permite mover el directorio sin romper la BD.
        """
        if not screenshot_b64:
            return ""

        project_dir = settings.baselines_path / project
        project_dir.mkdir(parents=True, exist_ok=True)

        filename = f"{abs(hash(selector))}.png"
        path = project_dir / filename

        try:
            path.write_bytes(base64.b64decode(screenshot_b64))
            log.debug("Snapshot guardado: %s", path)
        except Exception as exc:
            log.warning("No se pudo guardar snapshot: %s", exc)
            return ""

        # Relativa a baselines_path → "healing_demo/3056690626893589432.png"
        return str(Path(project) / filename)

    def _delete_snapshot(self, relative_path: str) -> None:
        """Elimina el archivo PNG de disco dado su path relativo en BD."""
        if not relative_path:
            return
        full_path = settings.baselines_path / relative_path
        try:
            full_path.unlink(missing_ok=True)
            log.debug("Snapshot eliminado: %s", full_path)
        except Exception as exc:
            log.warning("No se pudo eliminar snapshot %s: %s", full_path, exc)

    async def delete(self, selector: str, project: str) -> bool:
        """
        Elimina el baseline de BD y su snapshot PNG de disco.
        Devuelve True si existía y fue eliminado.
        """
        row = await self.get_orm(selector, project)
        if row is None:
            return False
        self._delete_snapshot(row.visual_snapshot_path)
        await self._session.delete(row)
        await self._session.flush()
        log.info("Baseline eliminado: project=%s selector=%s", project, selector)
        return True

    async def cleanup_orphan_snapshots(self, project: str) -> int:
        """
        Borra archivos PNG en disco que ya no tienen fila en BD para el proyecto dado.
        Útil para mantenimiento periódico. Devuelve cantidad de archivos eliminados.
        """
        project_dir = settings.baselines_path / project
        if not project_dir.exists():
            return 0

        # Filenames activos en BD para este proyecto
        rows = await self.list_by_project(project)
        active_files = {
            Path(r.visual_snapshot_path).name
            for r in rows
            if r.visual_snapshot_path
        }

        removed = 0
        for png in project_dir.glob("*.png"):
            if png.name not in active_files:
                png.unlink(missing_ok=True)
                log.info("Huérfano eliminado: %s", png)
                removed += 1

        return removed
