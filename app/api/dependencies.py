from __future__ import annotations

from typing import AsyncGenerator

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.arbitrator import HealingArbitrator
from app.core.config import settings
from app.engines.cv import CVEngine
from app.engines.dom import DOMEngine
from app.storage.database import get_session
from app.storage.repositories import BaselineRepository, BaselineVersionRepository, HealingRepository, WeightsRepository


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with get_session() as session:
        yield session


async def get_baseline_repo(
    db: AsyncSession = Depends(get_db),
) -> BaselineRepository:
    return BaselineRepository(db)


async def get_healing_repo(
    db: AsyncSession = Depends(get_db),
) -> HealingRepository:
    return HealingRepository(db)


async def get_weights_repo(
    db: AsyncSession = Depends(get_db),
) -> WeightsRepository:
    return WeightsRepository(db)


async def get_baseline_version_repo(
    db: AsyncSession = Depends(get_db),
) -> BaselineVersionRepository:
    return BaselineVersionRepository(db)


async def get_arbitrator(
    baseline_repo: BaselineRepository = Depends(get_baseline_repo),
    healing_repo: HealingRepository = Depends(get_healing_repo),
    weights_repo: WeightsRepository = Depends(get_weights_repo),
) -> HealingArbitrator:
    engines = [
        DOMEngine(threshold=settings.dom_score_threshold),
        CVEngine(threshold=settings.cv_confidence_threshold),
    ]
    return HealingArbitrator(
        engines=engines,
        baseline_repo=baseline_repo,
        healing_repo=healing_repo,
        weights_repo=weights_repo,
    )
