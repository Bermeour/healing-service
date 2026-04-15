from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.core.config import settings
from app.core.exceptions import BaselineNotFound, HealingFailed, HealingServiceError
from app.core.logging import setup_logging


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Ciclo de vida de la aplicación.
    - Startup : crea directorios, configura logging, inicializa la BD.
    - Shutdown: FastAPI cierra el pool de conexiones automáticamente.
    """
    settings.create_dirs()
    setup_logging(settings.log_level, settings.log_file)

    # Imports internos aquí para que el logging esté configurado primero
    import logging
    log = logging.getLogger("healing.startup")
    log.info("Self-Healing Service v1.0 [%s]", settings.app_env)
    log.info("Escuchando en %s:%s", settings.host, settings.port)
    log.info("Base de datos: %s [%s]", settings.db_url, settings.db_dialect)

    from app.storage.database import init_db
    await init_db()
    log.info("Base de conocimiento lista")

    yield

    log.info("Apagando Self-Healing Service...")


app = FastAPI(
    title="Self-Healing Service",
    version="1.0.0",
    lifespan=lifespan,
    # Swagger/ReDoc solo disponibles en development para no exponer la API en producción
    docs_url="/docs" if settings.is_dev else None,
    redoc_url="/redoc" if settings.is_dev else None,
)


# ── Manejadores de error globales ─────────────────────────────────────────────
# Convierten excepciones de dominio en respuestas HTTP con el código correcto.
# Sin estos handlers, FastAPI devolvería siempre 500 para cualquier excepción.

@app.exception_handler(BaselineNotFound)
async def baseline_not_found_handler(request: Request, exc: BaselineNotFound):
    return JSONResponse(status_code=404, content={"detail": str(exc)})


@app.exception_handler(HealingFailed)
async def healing_failed_handler(request: Request, exc: HealingFailed):
    # 422 Unprocessable: la petición era válida pero ningún motor resolvió el elemento
    return JSONResponse(status_code=422, content={"detail": str(exc)})


@app.exception_handler(HealingServiceError)
async def healing_service_error_handler(request: Request, exc: HealingServiceError):
    return JSONResponse(status_code=500, content={"detail": str(exc)})


# ── Routers ───────────────────────────────────────────────────────────────────
# El import va al final para evitar importaciones circulares:
# los routers importan dependencias que dependen de `app` a través de FastAPI.
from app.api.routes import baseline_router, heal_router, monitor_router  # noqa: E402

app.include_router(heal_router)        # POST /heal
app.include_router(baseline_router)    # POST /baseline/register, GET/DELETE /baseline/...
app.include_router(monitor_router)     # GET /health, /metrics, /history
