from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

log = logging.getLogger("healing.engine.cv.template")


@dataclass
class MatchResult:
    found: bool
    x: int
    y: int
    confidence: float
    method: str  # "TM_CCOEFF_NORMED" | "TM_SSIM_APPROX"


def _get_methods():
    import cv2
    return [
        ("TM_CCOEFF_NORMED", cv2.TM_CCOEFF_NORMED),
        ("TM_CCORR_NORMED",  cv2.TM_CCORR_NORMED),
    ]


def match_template(
    screenshot_path: str | Path,
    template_path: str | Path,
    threshold: float = 0.82,
) -> MatchResult:
    """
    Busca el template (snapshot del baseline) dentro del screenshot actual
    usando correlación normalizada de OpenCV.

    Prueba múltiples métodos en orden y devuelve el de mayor confianza.
    Retorna las coordenadas del CENTRO del elemento encontrado.

    cv2 se importa de forma lazy para que el módulo pueda cargarse
    incluso si opencv-python no está instalado (el motor CV simplemente
    no estará disponible, pero el servicio sigue funcionando con DOM).
    """
    import cv2  # lazy: no rompe el import del módulo si cv2 no está instalado

    screen_gray = _load_gray(screenshot_path)
    template_gray = _load_gray(template_path)

    if screen_gray is None or template_gray is None:
        log.error("No se pudo cargar imagen: screen=%s template=%s", screenshot_path, template_path)
        return MatchResult(found=False, x=0, y=0, confidence=0.0, method="FAILED")

    th, tw = template_gray.shape[:2]

    # Si el template es más grande que el screenshot, no puede funcionar
    sh, sw = screen_gray.shape[:2]
    if th > sh or tw > sw:
        log.warning("Template (%dx%d) más grande que screenshot (%dx%d)", tw, th, sw, sh)
        return MatchResult(found=False, x=0, y=0, confidence=0.0, method="FAILED")

    best: MatchResult | None = None

    for method_name, method in _get_methods():
        result = cv2.matchTemplate(screen_gray, template_gray, method)
        _, max_val, _, max_loc = cv2.minMaxLoc(result)

        log.debug("Método %s → confianza=%.3f", method_name, max_val)

        if best is None or max_val > best.confidence:
            center_x = max_loc[0] + tw // 2
            center_y = max_loc[1] + th // 2
            best = MatchResult(
                found=max_val >= threshold,
                x=center_x,
                y=center_y,
                confidence=round(float(max_val), 4),
                method=method_name,
            )

    return best  # type: ignore[return-value]


def _load_gray(path: str | Path):
    import cv2
    img = cv2.imread(str(path), cv2.IMREAD_GRAYSCALE)
    return img if img is not None else None
