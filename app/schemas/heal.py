from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field, field_validator


class HealRequest(BaseModel):
    selector_type: Literal["xpath", "css"] = Field(
        description="Tipo de selector que falló"
    )
    selector_value: str = Field(
        min_length=1,
        description="El selector que falló (XPath o CSS)",
    )
    dom_html: str = Field(
        min_length=1,
        description="page_source actual del browser",
    )
    screenshot_base64: Optional[str] = Field(
        default=None,
        description="Captura actual de pantalla en base64 (requerida para motor CV)",
    )
    test_id: str = Field(
        default="unknown",
        description="Identificador del test — para trazabilidad en el historial",
    )
    project: str = Field(
        min_length=1,
        description="Nombre del proyecto o cliente (ej: 'banco_xyz', 'portal_rrhh')",
    )
    scoring_profile: str = Field(
        default="default",
        description=(
            "Perfil de pesos del scorer DOM. "
            "Valores: 'default' | 'siebel' | 'angular' | 'legacy'. "
            "Controla qué atributos tienen más peso al buscar el elemento."
        ),
    )

    # ── Filtros de contexto (opcionales) ────────────────────────────────────────
    exclude_ids: list[str] = Field(
        default_factory=list,
        description="IDs de elementos a excluir del scoring (ej: botones del header).",
    )
    container_id: Optional[str] = Field(
        default=None,
        description="Solo buscar dentro del contenedor con este id.",
    )
    container_class: Optional[str] = Field(
        default=None,
        description=(
            "Solo buscar dentro de contenedores con estas clases. "
            "Espacio = AND, coma = OR. Ej: 'modal-body' o 'form-section,main-content'."
        ),
    )
    form_id: Optional[str] = Field(
        default=None,
        description="Solo buscar dentro del formulario con este id.",
    )
    anchors: list[dict] = Field(
        default_factory=list,
        description=(
            "Elementos de referencia para mejorar el scoring por proximidad DOM. "
            "Cada anchor: {type: 'id'|'text'|'css', value: str, weight: int}. "
            "Mayor weight = más influencia en el score del candidato cercano."
        ),
    )

    @field_validator("selector_value")
    @classmethod
    def strip_selector(cls, v: str) -> str:
        return v.strip()

    @field_validator("project")
    @classmethod
    def normalize_project(cls, v: str) -> str:
        return v.strip().lower()


class HealResponse(BaseModel):
    healed: bool = Field(description="True si algún motor encontró el elemento")
    new_selector: str = Field(description="Selector reparado listo para usar")
    selector_type: str = Field(
        description="Tipo del selector reparado: 'xpath' | 'css' | 'coords'"
    )
    strategy_used: str = Field(description="Motor que resolvió: 'DOM' | 'CV' | 'FAILED'")
    confidence: float = Field(ge=0.0, le=1.0, description="Nivel de confianza 0.0–1.0")
    message: str = Field(description="Descripción del resultado")
    healing_event_id: Optional[int] = Field(
        default=None,
        description="ID del evento guardado — úsalo para enviar feedback via POST /feedback",
    )
    from_cache: bool = Field(
        default=False,
        description="True si la respuesta provino del caché en memoria",
    )


class FeedbackRequest(BaseModel):
    healing_event_id: int = Field(description="ID del evento de sanación (de HealResponse)")
    correct: bool = Field(
        description="True si el selector encontrado funcionó correctamente en el test"
    )
    confirmed_selector: Optional[str] = Field(
        default=None,
        description="Selector que realmente funcionó (opcional, si correct=False y lo conoces)",
    )


class FeedbackResponse(BaseModel):
    healing_event_id: int
    correct: bool
    confirmed_selector: Optional[str] = None
    message: str
