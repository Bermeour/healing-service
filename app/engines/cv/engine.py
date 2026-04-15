from __future__ import annotations

import base64
import logging
import tempfile
from pathlib import Path

from app.core.config import settings
from app.engines.base import ElementBaseline, EngineResult, HealingEngine
from app.engines.cv.coords_resolver import encode_coords
from app.engines.cv.model_loader import get_detector
from app.engines.cv.template_matcher import match_template

log = logging.getLogger("healing.engine.cv")


class CVEngine(HealingEngine):
    """
    Motor de self-healing basado en visión por computador.

    Estrategia (en orden de costo computacional):
    1. Template matching con OpenCV  — rápido, sin modelo
    2. YOLO-nano local (opcional)    — más robusto, requiere modelo ONNX

    El motor solo se activa si el contexto incluye screenshot_b64
    y el baseline tiene visual_snapshot_path válido.
    """

    def __init__(
        self,
        threshold: float | None = None,
        yolo_model_path: str | Path | None = None,
    ) -> None:
        self._threshold = threshold or settings.cv_confidence_threshold
        self._yolo_path = yolo_model_path

    @property
    def name(self) -> str:
        return "CV"

    async def heal(self, context: dict) -> EngineResult:
        baseline: ElementBaseline = context["baseline"]
        screenshot_b64: str | None = context.get("screenshot_b64")

        if not screenshot_b64:
            return EngineResult.failed("CV", "No se proporcionó screenshot — CV no puede operar")

        if not baseline.visual_snapshot_path:
            return EngineResult.failed("CV", "El baseline no tiene snapshot visual registrado")

        template_path = Path(baseline.visual_snapshot_path)
        if not template_path.exists():
            return EngineResult.failed(
                "CV", f"Snapshot visual no encontrado: {template_path}"
            )

        # Escribe el screenshot actual en un archivo temporal
        with tempfile.NamedTemporaryFile(delete=False, suffix=".png") as tmp:
            tmp.write(base64.b64decode(screenshot_b64))
            current_path = Path(tmp.name)

        try:
            result = await self._run_template_matching(current_path, template_path)
            if result.found:
                return result

            # Intenta YOLO si template matching no fue suficiente
            result = await self._run_yolo(current_path, result.confidence)
            return result

        finally:
            current_path.unlink(missing_ok=True)

    async def _run_template_matching(
        self, current_path: Path, template_path: Path
    ) -> EngineResult:
        match = match_template(current_path, template_path, self._threshold)

        log.debug(
            "Template matching → confianza=%.3f (umbral=%.2f) método=%s",
            match.confidence, self._threshold, match.method,
        )

        if not match.found:
            return EngineResult.failed(
                "CV",
                f"Template matching: confianza {match.confidence:.2f} < umbral {self._threshold:.2f}",
                confidence=match.confidence,
            )

        selector = encode_coords(match.x, match.y)
        return EngineResult(
            found=True,
            selector=selector,
            selector_type="coords",
            confidence=match.confidence,
            strategy="CV",
            message=f"Sanado por template matching (conf={match.confidence:.2f})",
        )

    async def _run_yolo(self, current_path: Path, prev_confidence: float) -> EngineResult:
        detector = get_detector(self._yolo_path, self._threshold)

        if detector is None:
            return EngineResult.failed(
                "CV",
                "Template matching insuficiente y YOLO no está configurado",
                confidence=prev_confidence,
            )

        detection = detector.detect(current_path)
        log.debug("YOLO → confianza=%.3f", detection.confidence)

        if not detection.found:
            return EngineResult.failed(
                "CV",
                f"YOLO: confianza {detection.confidence:.2f} < umbral {self._threshold:.2f}",
                confidence=detection.confidence,
            )

        selector = encode_coords(detection.x, detection.y)
        return EngineResult(
            found=True,
            selector=selector,
            selector_type="coords",
            confidence=detection.confidence,
            strategy="CV",
            message=f"Sanado por YOLO (conf={detection.confidence:.2f})",
        )

    async def capture_baseline(self, context: dict) -> ElementBaseline:
        """
        El baseline visual se guarda desde el cliente (el cliente tiene acceso
        al driver y puede recortar el elemento). El servicio solo registra la ruta.
        """
        meta = context.get("element_meta", {})
        return ElementBaseline(
            tag=meta.get("tag", ""),
            xpath_original=context.get("xpath_original", ""),
            visual_snapshot_path=context.get("visual_snapshot_path", ""),
        )
