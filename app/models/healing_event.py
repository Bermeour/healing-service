from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.baseline import Base


class HealingEvent(Base):
    """
    Registro de cada sanación exitosa.
    Es la base de conocimiento que la IA usará para aprender patrones.
    """
    __tablename__ = "healing_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # Relación con el baseline
    baseline_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("baselines.id", ondelete="CASCADE"), nullable=False, index=True
    )
    baseline: Mapped["Baseline"] = relationship(back_populates=None, lazy="select")  # type: ignore[name-defined]

    # Contexto de la ejecución
    project: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    test_id: Mapped[str] = mapped_column(String(255), nullable=False, default="")

    # Qué falló y qué se encontró
    original_selector: Mapped[str] = mapped_column(Text, nullable=False)
    healed_selector: Mapped[str] = mapped_column(Text, nullable=False)
    selector_type: Mapped[str] = mapped_column(String(20), nullable=False)  # xpath | css | coords

    # Motor que resolvió
    strategy: Mapped[str] = mapped_column(String(20), nullable=False)   # DOM | CV
    confidence: Mapped[float] = mapped_column(Float, nullable=False)

    # Auditoría
    healed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # Feedback explícito del cliente (POST /feedback)
    feedback_correct: Mapped[bool | None] = mapped_column(Boolean, nullable=True, default=None)
    confirmed_selector: Mapped[str | None] = mapped_column(Text, nullable=True, default=None)
    feedback_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, default=None)

    __table_args__ = (
        Index("ix_healing_events_project_test", "project", "test_id"),
        Index("ix_healing_events_healed_at", "healed_at"),
    )
