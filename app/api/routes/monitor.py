from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, Query

from app.api.dependencies import get_healing_repo, get_weights_repo
from app.core.config import settings
from app.schemas.monitor import (
    HealthResponse,
    HealingEventResponse,
    HistoryResponse,
    MetricsResponse,
    StrategyStats,
)
from app.storage.repositories.healing_repo import HealingRepository
from app.storage.repositories.weights_repo import WeightsRepository

router = APIRouter(tags=["monitor"])


@router.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    """Verifica que el servicio está operativo. Útil para probes de Kubernetes/Docker."""
    return HealthResponse(
        status="ok",
        version="1.0.0",
        environment=settings.app_env,
        timestamp=datetime.utcnow(),
    )


@router.get("/metrics/{project}", response_model=MetricsResponse)
async def metrics(
    project: str,
    repo: HealingRepository = Depends(get_healing_repo),
) -> MetricsResponse:
    """
    Estadísticas de sanaciones agrupadas por proyecto.
    Muestra total, distribución por motor y confianza promedio.
    """
    stats = await repo.get_stats(project.lower())
    return MetricsResponse(
        project=stats["project"],
        total_healings=stats["total_healings"],
        by_strategy=StrategyStats(**stats["by_strategy"]),
        avg_confidence=stats["avg_confidence"],
    )


@router.post("/learn/{project}", tags=["AI"])
async def trigger_learning(
    project: str,
    repo: WeightsRepository = Depends(get_weights_repo),
) -> dict:
    """
    Dispara el aprendizaje de pesos adaptativos para un proyecto.
    Analiza el historial de sanaciones DOM y ajusta los pesos del scorer.

    Se ejecuta automáticamente cada 10 sanaciones DOM exitosas.
    Llamar manualmente si se quiere forzar el re-entrenamiento.
    """
    stats = await repo.run_learning(project.lower())
    return {"project": project.lower(), **stats}


@router.get("/weights/{project}", tags=["AI"])
async def get_weights(
    project: str,
    repo: WeightsRepository = Depends(get_weights_repo),
) -> dict:
    """
    Devuelve los pesos aprendidos para un proyecto.
    Si no hay pesos aprendidos aún, indica que se usan los pesos base ('default').
    """
    record = await repo.get(project.lower())
    if record is None:
        return {
            "project": project.lower(),
            "status": "usando pesos base — aún no hay suficientes datos",
            "weights": None,
            "sample_size": 0,
        }
    return {
        "project": project.lower(),
        "status": "pesos aprendidos activos",
        "weights": record.weights,
        "sample_size": record.sample_size,
        "avg_confidence": record.avg_confidence,
        "learned_at": record.learned_at.isoformat(),
    }


@router.get("/cache/stats", tags=["monitor"])
async def cache_stats() -> dict:
    """
    Estadísticas del caché en memoria de resultados de healing.
    Muestra cuántas entradas están activas y la configuración de TTL.
    """
    from app.core.cache import get_cache
    return get_cache().stats()


@router.delete("/cache/{project}", tags=["monitor"])
async def invalidate_cache(project: str) -> dict:
    """
    Invalida todas las entradas del caché para un proyecto.
    Útil tras despliegues o cambios masivos de UI.
    """
    from app.core.cache import get_cache
    removed = get_cache().invalidate_project(project.lower())
    return {"project": project.lower(), "entries_removed": removed}


@router.get("/history/{project}", response_model=HistoryResponse)
async def history(
    project: str,
    test_id: str | None = Query(default=None, description="Filtra por test específico"),
    limit: int = Query(default=50, ge=1, le=500, description="Máximo de registros"),
    repo: HealingRepository = Depends(get_healing_repo),
) -> HistoryResponse:
    """
    Historial de sanaciones de un proyecto.
    Permite filtrar por `test_id` y limitar la cantidad de resultados.
    """
    events = await repo.get_history(
        project=project.lower(),
        test_id=test_id,
        limit=limit,
    )
    return HistoryResponse(
        project=project.lower(),
        total=len(events),
        items=[HealingEventResponse.from_orm(e) for e in events],
    )
