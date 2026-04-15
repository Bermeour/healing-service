from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, Index, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.baseline import Base


class BaselineVersion(Base):
    """
    Historial de cambios de un baseline.

    Cada vez que un baseline se actualiza (manualmente vía /register o
    automáticamente tras una sanación de alta confianza) se guarda la
    huella anterior aquí antes de sobreescribir.

    Permite auditar la evolución del elemento y hacer rollback si una
    actualización automática fue incorrecta.
    """
    __tablename__ = "baseline_versions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # Referencia al baseline activo (no CASCADE — queremos historial aunque se borre el baseline)
    baseline_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("baselines.id", ondelete="SET NULL"), nullable=True
    )

    # Copia de los datos al momento del snapshot
    project: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    selector_value: Mapped[str] = mapped_column(Text, nullable=False)
    selector_type: Mapped[str] = mapped_column(String(20), nullable=False)
    tag: Mapped[str] = mapped_column(String(50), nullable=False)
    element_meta: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    visual_snapshot_path: Mapped[str] = mapped_column(String(500), nullable=False, default="")

    # Número de versión incremental por baseline (1 = primera versión guardada antes del primer update)
    version_number: Mapped[int] = mapped_column(Integer, nullable=False, default=1)

    # Origen del cambio que provocó este snapshot
    reason: Mapped[str] = mapped_column(
        String(30), nullable=False, default="manual"
        # "manual" = /baseline/register  |  "auto_update" = post-sanación de alta confianza
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    __table_args__ = (
        Index("ix_baseline_versions_project_selector", "project", "selector_value"),
        Index("ix_baseline_versions_baseline_id", "baseline_id"),
    )
