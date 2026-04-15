from __future__ import annotations

import logging

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException

from app.api.dependencies import get_arbitrator, get_healing_repo, get_weights_repo
from app.core.arbitrator import HealingArbitrator
from app.core.cache import get_cache
from app.schemas.heal import FeedbackRequest, FeedbackResponse, HealRequest, HealResponse
from app.storage.repositories.healing_repo import HealingRepository
from app.storage.repositories.weights_repo import WeightsRepository

router = APIRouter(prefix="/heal", tags=["self-healing"])
log = logging.getLogger("healing.routes.heal")

# Cada cuántas sanaciones DOM exitosas se re-entrena el modelo de pesos
_LEARN_EVERY = 10
_dom_heal_counts: dict[str, int] = {}   # contador en memoria por proyecto


@router.post("", response_model=HealResponse, status_code=200)
async def heal(
    request: HealRequest,
    background_tasks: BackgroundTasks,
    arbitrator: HealingArbitrator = Depends(get_arbitrator),
    weights_repo: WeightsRepository = Depends(get_weights_repo),
) -> HealResponse:
    """
    Intenta reparar un selector roto usando los motores DOM y CV en orden.

    - Motor **DOM**: analiza el HTML actual y busca el elemento por scoring de atributos.
    - Motor **CV**: usa visión por computador si DOM no alcanza el umbral.

    Devuelve 404 si no hay baseline registrado para el selector.
    Devuelve 422 si ningún motor encontró el elemento.
    """
    log.info(
        "Solicitud de sanación | project=%s test=%s selector=%s",
        request.project, request.test_id, request.selector_value[:60],
    )

    result = await arbitrator.heal(request)

    # Auto-aprendizaje: cada _LEARN_EVERY sanaciones DOM exitosas por proyecto
    if result.found and result.strategy == "DOM":
        project = request.project
        _dom_heal_counts[project] = _dom_heal_counts.get(project, 0) + 1
        if _dom_heal_counts[project] % _LEARN_EVERY == 0:
            log.info(
                "Disparando aprendizaje en background para project=%s (n=%d)",
                project, _dom_heal_counts[project],
            )
            background_tasks.add_task(_run_learning_bg, project)

    from_cache = getattr(result, "_from_cache", False)
    return HealResponse(
        healed=result.found,
        new_selector=result.selector,
        selector_type=result.selector_type,
        strategy_used=result.strategy,
        confidence=result.confidence,
        message=result.message,
        healing_event_id=getattr(result, "_event_id", None),
        from_cache=from_cache,
    )


@router.post("/feedback", response_model=FeedbackResponse, tags=["AI"])
async def feedback(
    request: FeedbackRequest,
    healing_repo: HealingRepository = Depends(get_healing_repo),
) -> FeedbackResponse:
    """
    Registra si el selector encontrado por el healing fue correcto en la ejecución real.

    El cliente debe llamar a este endpoint después de ejecutar el test con el selector
    reparado, indicando si funcionó (`correct=true`) o no (`correct=false`).

    Cuando `correct=false`, la entrada del caché se invalida para que la próxima
    sanación reintente los motores en vez de devolver el resultado incorrecto.

    El `healing_event_id` viene en la respuesta del `POST /heal`.
    """
    event = await healing_repo.save_feedback(
        event_id=request.healing_event_id,
        correct=request.correct,
        confirmed_selector=request.confirmed_selector,
    )
    if event is None:
        raise HTTPException(
            status_code=404,
            detail=f"No existe el evento de sanación con id={request.healing_event_id}",
        )

    # Si el feedback fue negativo, invalida la caché para este elemento
    if not request.correct:
        get_cache().invalidate(event.project, event.original_selector)
        log.info(
            "Caché invalidado por feedback negativo | project=%s selector=%.60s",
            event.project, event.original_selector,
        )

    return FeedbackResponse(
        healing_event_id=event.id,
        correct=request.correct,
        confirmed_selector=request.confirmed_selector,
        message="Feedback registrado correctamente",
    )


async def _run_learning_bg(project: str) -> None:
    """Tarea background — abre su propia sesión para no bloquear el request."""
    from app.storage.database import get_session
    try:
        async with get_session() as session:
            repo = WeightsRepository(session)
            stats = await repo.run_learning(project)
            log.info("Aprendizaje background completado: %s", stats)
    except Exception as exc:
        log.error("Error en aprendizaje background project=%s: %s", project, exc)
