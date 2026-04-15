from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.core.config import settings
from app.models import Base

log = logging.getLogger("healing.storage.database")


def _build_engine():
    """
    Construye el engine AsyncSQLAlchemy según el dialecto configurado en DB_URL.

    SQLite  → NullPool + WAL mode via event hook (un archivo local, sin pool)
    MSSQL   → pool de conexiones estándar + fast_executemany
    Otros   → configuración genérica (PostgreSQL, MySQL, etc.)
    """
    dialect = settings.db_dialect

    if dialect == "sqlite":
        engine = create_async_engine(
            settings.db_url,
            echo=False,
            poolclass=NullPool,          # SQLite no soporta pool multi-thread con async
            connect_args={
                "timeout": 30,           # segundos antes de "database is locked"
                "check_same_thread": False,
            },
        )

        # WAL mode en cada conexión nueva — mejor que hacerlo en init_db()
        # porque aplica aunque el pool recree la conexión
        @event.listens_for(engine.sync_engine, "connect")
        def _set_sqlite_pragmas(dbapi_conn, _record):
            cursor = dbapi_conn.cursor()
            cursor.execute("PRAGMA journal_mode=WAL")
            cursor.execute("PRAGMA synchronous=NORMAL")   # seguro con WAL, más rápido
            cursor.execute("PRAGMA busy_timeout=30000")   # reintenta 30 s antes de error
            cursor.execute("PRAGMA cache_size=-32000")    # ~32 MB de caché en memoria
            cursor.close()

        return engine

    if dialect == "mssql":
        return create_async_engine(
            settings.db_url,
            echo=False,
            pool_pre_ping=True,
            pool_size=10,
            max_overflow=20,
            pool_timeout=30,
            pool_recycle=1800,           # recicla conexiones cada 30 min
            execution_options={"fast_executemany": True},
        )

    # Genérico (PostgreSQL, MySQL…)
    return create_async_engine(
        settings.db_url,
        echo=False,
        pool_pre_ping=True,
        pool_size=10,
        max_overflow=20,
        pool_recycle=1800,
    )


# Engine único para toda la aplicación (singleton por módulo)
_engine = _build_engine()

_session_factory = async_sessionmaker(
    bind=_engine,
    class_=AsyncSession,
    expire_on_commit=False,  # evita lazy loads después del commit
    autoflush=False,
)


async def init_db() -> None:
    """Crea todas las tablas si no existen. Llamar una vez al startup."""
    async with _engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    log.info(
        "DB [%s] — tablas verificadas: %s",
        settings.db_dialect,
        list(Base.metadata.tables.keys()),
    )


async def close_db() -> None:
    """Cierra el pool de conexiones. Llamar al shutdown."""
    await _engine.dispose()
    log.info("Pool de base de datos cerrado")


@asynccontextmanager
async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """
    Context manager que provee una sesión async con commit/rollback automático.

    Uso directo:
        async with get_session() as session:
            ...

    Vía FastAPI Depends (en dependencies.py):
        async def get_db():
            async with get_session() as session:
                yield session
    """
    async with _session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
