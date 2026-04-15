from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import JSON, DateTime, Index, Integer, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class Baseline(Base):
    """
    Huella de un elemento capturada cuando el test pasa por primera vez.
    Cada combinación (project, selector_value) tiene un único baseline activo.
    """
    __tablename__ = "baselines"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # Identificación
    project: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    selector_type: Mapped[str] = mapped_column(String(20), nullable=False)   # xpath | css
    selector_value: Mapped[str] = mapped_column(Text, nullable=False)

    # Huella DOM
    tag: Mapped[str] = mapped_column(String(50), nullable=False)
    element_meta: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    # Guarda: id, name, text, classes, aria_label, placeholder, parent_tag,
    #         siblings_count, type, role, data_testid

    # Huella visual
    visual_snapshot_path: Mapped[str] = mapped_column(String(500), nullable=False, default="")

    # Auditoría
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    heal_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    __table_args__ = (
        Index("ix_baselines_project_selector", "project", "selector_value", unique=True),
    )

    def to_element_baseline(self):
        """Convierte el ORM model al dataclass que usan los motores."""
        from app.core.config import settings
        from app.engines.base import ElementBaseline
        meta = self.element_meta or {}

        # Resuelve la ruta visual: puede ser relativa (nueva) o absoluta (migración)
        visual_path = self.visual_snapshot_path or ""
        if visual_path and not Path(visual_path).is_absolute():
            visual_path = str(settings.baselines_path / visual_path)

        return ElementBaseline(
            tag=self.tag,
            xpath_original=self.selector_value,
            id=meta.get("id", ""),
            name=meta.get("name", ""),
            text=meta.get("text", ""),
            classes=meta.get("classes", []),
            aria_label=meta.get("aria_label", ""),
            placeholder=meta.get("placeholder", ""),
            parent_tag=meta.get("parent_tag", ""),
            siblings_count=meta.get("siblings_count", 0),
            visual_snapshot_path=visual_path,
            type=meta.get("type", ""),
            role=meta.get("role", ""),
            data_testid=meta.get("data_testid", ""),
        )
