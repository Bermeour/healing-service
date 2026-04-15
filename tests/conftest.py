from __future__ import annotations

import asyncio
import base64
from pathlib import Path
from typing import AsyncGenerator
from unittest.mock import AsyncMock, MagicMock

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import settings
from app.engines.base import ElementBaseline
from app.models import Base
from app.storage.repositories.baseline_repo import BaselineRepository
from app.storage.repositories.healing_repo import HealingRepository

# ── Event loop (una sola instancia para toda la sesión) ───────────────────────

@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


# ── Base de datos en memoria para tests ───────────────────────────────────────

@pytest_asyncio.fixture(scope="session")
async def test_engine():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest_asyncio.fixture
async def db_session(test_engine) -> AsyncGenerator[AsyncSession, None]:
    factory = async_sessionmaker(test_engine, expire_on_commit=False, autoflush=False)
    async with factory() as session:
        yield session
        await session.rollback()  # cada test empieza limpio


@pytest_asyncio.fixture
async def baseline_repo(db_session: AsyncSession) -> BaselineRepository:
    return BaselineRepository(db_session)


@pytest_asyncio.fixture
async def healing_repo(db_session: AsyncSession) -> HealingRepository:
    return HealingRepository(db_session)


# ── Cliente HTTP para tests de integración ────────────────────────────────────

@pytest_asyncio.fixture
async def api_client() -> AsyncGenerator[AsyncClient, None]:
    """
    Cliente HTTP que habla directamente con la app FastAPI en memoria.
    Un único engine SQLite compartido por todos los requests del mismo test.
    """
    from main import app
    from app.api.dependencies import get_db

    # Engine compartido — todos los requests del mismo test usan la misma BD
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    factory = async_sessionmaker(engine, expire_on_commit=False, autoflush=False)

    async def override_get_db():
        async with factory() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    app.dependency_overrides[get_db] = override_get_db

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        yield client

    app.dependency_overrides.clear()
    await engine.dispose()


# ── Fixtures de datos ─────────────────────────────────────────────────────────

@pytest.fixture
def sample_baseline() -> ElementBaseline:
    return ElementBaseline(
        tag="button",
        xpath_original="//button[@id='btn-submit']",
        id="btn-submit",
        name="",
        text="Iniciar sesión",
        classes=["btn", "btn-primary"],
        aria_label="",
        placeholder="",
        parent_tag="form",
        siblings_count=1,
        type="submit",
    )


@pytest.fixture
def sample_dom() -> str:
    return """
    <html><body>
      <form>
        <input type="text" id="username" name="username" placeholder="Usuario"/>
        <input type="password" id="password" name="password" placeholder="Contraseña"/>
        <button id="btn-submit" class="btn btn-primary" type="submit">Iniciar sesión</button>
        <button id="btn-cancel" class="btn btn-secondary" type="button">Cancelar</button>
      </form>
    </body></html>
    """


@pytest.fixture
def changed_dom() -> str:
    """DOM donde el id cambió pero el texto, clases y type se mantienen."""
    return """
    <html><body>
      <form>
        <input type="text" id="user-field" name="username" placeholder="Usuario"/>
        <input type="password" id="pass-field" name="password" placeholder="Contraseña"/>
        <button id="new-submit-id" class="btn btn-primary" type="submit">Iniciar sesión</button>
        <button id="new-cancel-id" class="btn btn-secondary" type="button">Cancelar</button>
      </form>
    </body></html>
    """


@pytest.fixture
def blank_png_b64() -> str:
    """PNG 1x1 en base64 — suficiente para tests que requieren screenshot."""
    return base64.b64encode(
        b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01"
        b"\x00\x00\x00\x01\x08\x02\x00\x00\x00\x90wS\xde\x00\x00"
        b"\x00\x0cIDATx\x9cc\xf8\x0f\x00\x00\x01\x01\x00\x05\x18"
        b"\xd8N\x00\x00\x00\x00IEND\xaeB`\x82"
    ).decode()


@pytest.fixture
def baseline_request_payload() -> dict:
    return {
        "selector_type":  "xpath",
        "selector_value": "//button[@id='btn-submit']",
        "screenshot_base64": base64.b64encode(
            b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01"
            b"\x00\x00\x00\x01\x08\x02\x00\x00\x00\x90wS\xde\x00\x00"
            b"\x00\x0cIDATx\x9cc\xf8\x0f\x00\x00\x01\x01\x00\x05\x18"
            b"\xd8N\x00\x00\x00\x00IEND\xaeB`\x82"
        ).decode(),
        "element_meta": {
            "tag":            "button",
            "id":             "btn-submit",
            "name":           "",
            "text":           "Iniciar sesión",
            "classes":        ["btn", "btn-primary"],
            "aria_label":     "",
            "placeholder":    "",
            "parent_tag":     "form",
            "siblings_count": 1,
            "type":           "submit",
            "role":           "",
            "data_testid":    "",
        },
        "test_id": "test_login",
        "project": "test_project",
    }
