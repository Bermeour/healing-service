from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import DateTime, Integer, JSON, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.baseline import Base


class LearnedWeights(Base):
    """
    Pesos del DOM scorer aprendidos automáticamente del historial de sanaciones.

    Por cada proyecto se guarda un único registro (upsert).
    El campo weights es un dict attr → peso entero, con la misma estructura
    que WEIGHT_PROFILES en scorer.py — el engine lo usa directamente.
    """
    __tablename__ = "learned_weights"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # Un registro por proyecto
    project: Mapped[str] = mapped_column(String(120), nullable=False, unique=True, index=True)

    # Los pesos aprendidos: {"id": 42, "name": 38, "aria_label": 29, ...}
    weights: Mapped[dict] = mapped_column(JSON, nullable=False)

    # Cuántos eventos se usaron para aprenderlos
    sample_size: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    # Confianza promedio de los eventos usados para aprender
    avg_confidence: Mapped[float] = mapped_column(Integer, nullable=False, default=0)

    learned_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
