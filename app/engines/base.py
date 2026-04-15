from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass
class EngineResult:
    found: bool
    selector: str
    selector_type: str      # "xpath" | "css" | "coords"
    confidence: float       # 0.0 – 1.0
    strategy: str           # "DOM" | "CV" | "FAILED"
    message: str = ""
    # Metadatos internos — no forman parte de la respuesta pública
    _event_id: int | None = field(default=None, repr=False)
    _from_cache: bool = field(default=False, repr=False)

    @classmethod
    def failed(cls, strategy: str, message: str, confidence: float = 0.0) -> EngineResult:
        return cls(
            found=False,
            selector="",
            selector_type="",
            confidence=confidence,
            strategy=strategy,
            message=message,
        )


@dataclass
class ElementBaseline:
    """Huella de un elemento capturada cuando el test pasa por primera vez."""
    tag: str
    xpath_original: str
    id: str = ""
    name: str = ""
    text: str = ""
    classes: list[str] = field(default_factory=list)
    aria_label: str = ""
    placeholder: str = ""
    parent_tag: str = ""
    siblings_count: int = 0
    visual_snapshot_path: str = ""  # ruta al recorte PNG del elemento
    # Atributos extra para scoring
    type: str = ""
    role: str = ""
    data_testid: str = ""
    # Atributos enterprise / multi-framework
    data_cy: str = ""
    data_qa: str = ""
    formcontrolname: str = ""   # Angular reactive forms
    title: str = ""
    data_display: str = ""      # Siebel toolbars


class HealingEngine(ABC):
    """Contrato que deben cumplir todos los motores de self-healing."""

    @abstractmethod
    async def heal(self, context: dict) -> EngineResult:
        """
        Intenta encontrar el elemento en el estado actual de la UI.

        context keys:
            dom_html        str             page_source actual
            baseline        ElementBaseline huella del elemento
            screenshot_b64  str | None      captura actual en base64
        """
        ...

    @abstractmethod
    async def capture_baseline(self, context: dict) -> ElementBaseline:
        """
        Captura la huella inicial de un elemento.

        context keys:
            element_meta    dict    atributos del elemento (id, name, text, ...)
            dom_snapshot    str     HTML del elemento y su contexto
            screenshot_b64  str     imagen recortada del elemento en base64
            xpath_original  str     selector original
        """
        ...

    @property
    @abstractmethod
    def name(self) -> str:
        """Identificador del motor: 'DOM' | 'CV'"""
        ...
