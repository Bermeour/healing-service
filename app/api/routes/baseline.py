from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel

from app.api.dependencies import get_baseline_repo, get_baseline_version_repo
from app.schemas.baseline import (
    BaselineListResponse,
    BaselineRequest,
    BaselineResponse,
    BaselineVersionListResponse,
    BaselineVersionResponse,
)
from app.storage.repositories.baseline_repo import BaselineRepository
from app.storage.repositories.baseline_version_repo import BaselineVersionRepository

router = APIRouter(prefix="/baseline", tags=["baseline"])
log = logging.getLogger("healing.routes.baseline")


class CleanupResponse(BaseModel):
    project: str
    orphans_removed: int


@router.post("/register", response_model=BaselineResponse, status_code=201)
async def register_baseline(
    request: BaselineRequest,
    repo: BaselineRepository = Depends(get_baseline_repo),
) -> BaselineResponse:
    """
    Registra o actualiza la huella de un elemento.

    El cliente debe llamar a este endpoint la **primera vez** que encuentra
    el elemento (cuando el selector funciona) para guardar el baseline.
    Si el selector ya tiene un baseline, lo sobreescribe con la huella nueva.
    """
    log.info(
        "Registrando baseline | project=%s selector=%s",
        request.project, request.selector_value[:60],
    )
    row = await repo.register(request)
    return BaselineResponse.from_orm(row)


@router.get("/{project}", response_model=BaselineListResponse)
async def list_baselines(
    project: str,
    repo: BaselineRepository = Depends(get_baseline_repo),
) -> BaselineListResponse:
    """Lista todos los baselines registrados para un proyecto."""
    rows = await repo.list_by_project(project.lower())
    return BaselineListResponse(
        project=project.lower(),
        total=len(rows),
        items=[BaselineResponse.from_orm(r) for r in rows],
    )


@router.get("/{project}/{selector:path}", response_model=BaselineResponse)
async def get_baseline(
    project: str,
    selector: str,
    repo: BaselineRepository = Depends(get_baseline_repo),
) -> BaselineResponse:
    """Consulta el baseline de un selector específico dentro de un proyecto."""
    row = await repo.get_orm(selector, project.lower())
    if row is None:
        raise HTTPException(
            status_code=404,
            detail=f"No hay baseline para selector='{selector}' en project='{project}'",
        )
    return BaselineResponse.from_orm(row)


@router.delete("/{project}/{selector:path}", status_code=204, response_class=Response)
async def delete_baseline(
    project: str,
    selector: str,
    repo: BaselineRepository = Depends(get_baseline_repo),
) -> Response:
    """
    Elimina el baseline de un selector y borra su snapshot PNG de disco.
    Útil cuando un elemento desaparece definitivamente de la UI.
    """
    deleted = await repo.delete(selector, project.lower())
    if not deleted:
        raise HTTPException(
            status_code=404,
            detail=f"No hay baseline para selector='{selector}' en project='{project}'",
        )
    return Response(status_code=204)


@router.post("/{project}/cleanup", response_model=CleanupResponse)
async def cleanup_orphans(
    project: str,
    repo: BaselineRepository = Depends(get_baseline_repo),
) -> CleanupResponse:
    """
    Elimina archivos PNG en disco que ya no tienen fila en BD para el proyecto.
    Llamar periódicamente o después de borrar baselines en lote.
    """
    removed = await repo.cleanup_orphan_snapshots(project.lower())
    log.info("Cleanup project=%s — %d huérfanos eliminados", project, removed)
    return CleanupResponse(project=project.lower(), orphans_removed=removed)


@router.get(
    "/{project}/{selector:path}/versions",
    response_model=BaselineVersionListResponse,
    tags=["baseline", "versioning"],
)
async def list_versions(
    project: str,
    selector: str,
    version_repo: BaselineVersionRepository = Depends(get_baseline_version_repo),
) -> BaselineVersionListResponse:
    """
    Devuelve el historial de versiones de un baseline.

    Cada vez que un baseline se actualiza (manualmente vía /register o
    automáticamente tras una sanación de alta confianza) se guarda la
    huella anterior como versión histórica.
    """
    versions = await version_repo.list_versions(project.lower(), selector)
    return BaselineVersionListResponse(
        project=project.lower(),
        selector_value=selector,
        total=len(versions),
        items=[BaselineVersionResponse.from_orm(v) for v in versions],
    )


@router.post(
    "/{project}/{selector:path}/rollback/{version_id}",
    response_model=BaselineResponse,
    tags=["baseline", "versioning"],
)
async def rollback_baseline(
    project: str,
    selector: str,
    version_id: int,
    repo: BaselineRepository = Depends(get_baseline_repo),
) -> BaselineResponse:
    """
    Restaura el baseline al estado de una versión histórica específica.

    Guarda el estado actual como versión antes de restaurar, por lo que
    el rollback es reversible. Usa `GET /versions` para ver el listado.

    También invalida el caché del selector para que la próxima sanación
    use la nueva huella.
    """
    from app.core.cache import get_cache

    updated = await repo.rollback_to_version(version_id)
    if updated is None:
        raise HTTPException(
            status_code=404,
            detail=f"Versión id={version_id} no encontrada para selector='{selector}' en project='{project}'",
        )

    get_cache().invalidate(project.lower(), selector)
    log.info(
        "Rollback exitoso | project=%s selector=%.60s version_id=%d",
        project, selector, version_id,
    )
    return BaselineResponse.from_orm(updated)
