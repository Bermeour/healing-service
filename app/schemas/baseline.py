from __future__ import annotations

from datetime import datetime
from typing import Any, Literal, Optional

from pydantic import BaseModel, Field, field_validator


class ElementMeta(BaseModel):
    """Atributos del elemento capturados por el cliente al registrar el baseline."""
    tag: str = Field(min_length=1, description="Tag HTML del elemento (input, button, a…)")
    id: str = ""
    name: str = ""
    text: str = ""
    classes: list[str] = Field(default_factory=list)
    aria_label: str = ""
    placeholder: str = ""
    parent_tag: str = ""
    siblings_count: int = 0
    # Atributos extra de scoring
    type: str = ""          # input[type=submit]
    role: str = ""          # role ARIA
    data_testid: str = ""   # data-testid

    def to_dict(self) -> dict[str, Any]:
        return self.model_dump()


class BaselineRequest(BaseModel):
    selector_type: Literal["xpath", "css"] = Field(
        description="Tipo de selector original"
    )
    selector_value: str = Field(
        min_length=1,
        description="Selector original que funciona (XPath o CSS)",
    )
    screenshot_base64: str = Field(
        min_length=1,
        description="Recorte del elemento en base64 — huella visual",
    )
    element_meta: ElementMeta = Field(
        description="Atributos del elemento capturados desde el DOM"
    )
    test_id: str = Field(default="unknown")
    project: str = Field(min_length=1)

    @field_validator("selector_value")
    @classmethod
    def strip_selector(cls, v: str) -> str:
        return v.strip()

    @field_validator("project")
    @classmethod
    def normalize_project(cls, v: str) -> str:
        return v.strip().lower()


class BaselineResponse(BaseModel):
    id: int
    project: str
    selector_type: str
    selector_value: str
    tag: str
    heal_count: int
    created_at: datetime
    updated_at: datetime
    has_visual_snapshot: bool = Field(
        description="True si hay snapshot visual guardado en disco"
    )

    @classmethod
    def from_orm(cls, row) -> BaselineResponse:
        return cls(
            id=row.id,
            project=row.project,
            selector_type=row.selector_type,
            selector_value=row.selector_value,
            tag=row.tag,
            heal_count=row.heal_count,
            created_at=row.created_at,
            updated_at=row.updated_at,
            has_visual_snapshot=bool(row.visual_snapshot_path),
        )


class BaselineListResponse(BaseModel):
    project: str
    total: int
    items: list[BaselineResponse]


class BaselineVersionResponse(BaseModel):
    id: int
    baseline_id: int | None
    project: str
    selector_value: str
    tag: str
    version_number: int
    reason: str
    created_at: datetime

    @classmethod
    def from_orm(cls, row) -> BaselineVersionResponse:
        return cls(
            id=row.id,
            baseline_id=row.baseline_id,
            project=row.project,
            selector_value=row.selector_value,
            tag=row.tag,
            version_number=row.version_number,
            reason=row.reason,
            created_at=row.created_at,
        )


class BaselineVersionListResponse(BaseModel):
    project: str
    selector_value: str
    total: int
    items: list[BaselineVersionResponse]
