from __future__ import annotations

from typing import Any, Generic, Sequence, Type, TypeVar

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.baseline import Base

ModelT = TypeVar("ModelT", bound=Base)


class BaseRepository(Generic[ModelT]):
    """CRUD genérico reutilizable para cualquier modelo ORM."""

    def __init__(self, session: AsyncSession, model: Type[ModelT]) -> None:
        self._session = session
        self._model = model

    async def get_by_id(self, pk: int) -> ModelT | None:
        return await self._session.get(self._model, pk)

    async def list_all(self, limit: int = 100, offset: int = 0) -> Sequence[ModelT]:
        result = await self._session.execute(
            select(self._model).limit(limit).offset(offset)
        )
        return result.scalars().all()

    async def save(self, instance: ModelT) -> ModelT:
        self._session.add(instance)
        await self._session.flush()   # asigna el id sin hacer commit
        return instance

    async def delete(self, instance: ModelT) -> None:
        await self._session.delete(instance)
        await self._session.flush()

    async def filter_by(self, **kwargs: Any) -> Sequence[ModelT]:
        conditions = [
            getattr(self._model, k) == v
            for k, v in kwargs.items()
        ]
        result = await self._session.execute(
            select(self._model).where(*conditions)
        )
        return result.scalars().all()
