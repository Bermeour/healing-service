from __future__ import annotations

import logging
from pathlib import Path
from dataclasses import dataclass

from app.core.exceptions import ModelNotLoaded

log = logging.getLogger("healing.engine.cv.model")


@dataclass
class DetectionResult:
    found: bool
    x: int
    y: int
    confidence: float
    class_id: int = 0


class YOLODetector:
    """
    Detector YOLO-nano/tiny que corre 100% local usando ONNX Runtime vía OpenCV DNN.
    No requiere internet ni GPU — funciona en CPU estándar.

    Uso previsto: respaldo cuando template matching no alcanza el umbral.
    El modelo ONNX debe estar entrenado con capturas de la propia aplicación.
    """

    # Tamaño de entrada esperado por YOLO-nano (configurable al cargar)
    INPUT_SIZE = (416, 416)

    def __init__(self, model_path: str | Path, threshold: float = 0.82) -> None:
        self._threshold = threshold
        self._net = self._load(Path(model_path))

    def _load(self, path: Path):
        import cv2  # lazy — no falla al importar el módulo si cv2 no está disponible

        if not path.exists():
            raise ModelNotLoaded(str(path))

        suffix = path.suffix.lower()
        if suffix == ".onnx":
            net = cv2.dnn.readNetFromONNX(str(path))
        elif suffix in (".weights",):
            cfg = path.with_suffix(".cfg")
            if not cfg.exists():
                raise ModelNotLoaded(f"Falta el .cfg para: {path}")
            net = cv2.dnn.readNetFromDarknet(str(cfg), str(path))
        else:
            raise ModelNotLoaded(f"Formato de modelo no soportado: {suffix}")

        net.setPreferableBackend(cv2.dnn.DNN_BACKEND_OPENCV)
        net.setPreferableTarget(cv2.dnn.DNN_TARGET_CPU)
        log.info("Modelo CV cargado desde: %s", path)
        return net

    def detect(self, screenshot_path: str | Path) -> DetectionResult:
        """
        Corre inferencia sobre el screenshot y devuelve la detección de mayor
        confianza. Retorna las coordenadas del centro del elemento.
        """
        import cv2
        import numpy as np

        image = cv2.imread(str(screenshot_path))
        if image is None:
            log.error("No se pudo cargar screenshot: %s", screenshot_path)
            return DetectionResult(found=False, x=0, y=0, confidence=0.0)

        h, w = image.shape[:2]
        blob = cv2.dnn.blobFromImage(
            image,
            scalefactor=1 / 255.0,
            size=self.INPUT_SIZE,
            swapRB=True,
            crop=False,
        )
        self._net.setInput(blob)

        output_layers = self._net.getUnconnectedOutLayersNames()
        outputs = self._net.forward(output_layers)

        best_conf = 0.0
        best_box: tuple[int, int, int, int] | None = None
        best_class = 0

        for output in outputs:
            for detection in output:
                scores = detection[5:]
                class_id = int(np.argmax(scores))
                confidence = float(scores[class_id])

                if confidence < self._threshold:
                    continue

                # YOLO devuelve coordenadas relativas al tamaño de entrada
                cx = int(detection[0] * w)
                cy = int(detection[1] * h)
                bw = int(detection[2] * w)
                bh = int(detection[3] * h)

                if confidence > best_conf:
                    best_conf = confidence
                    best_box = (cx - bw // 2, cy - bh // 2, bw, bh)
                    best_class = class_id

        if best_box is None:
            return DetectionResult(found=False, x=0, y=0, confidence=best_conf)

        bx, by, bw, bh = best_box
        return DetectionResult(
            found=True,
            x=bx + bw // 2,
            y=by + bh // 2,
            confidence=round(best_conf, 4),
            class_id=best_class,
        )


# Singleton opcional — se inicializa solo si hay modelo disponible
_detector: YOLODetector | None = None


def get_detector(model_path: str | Path | None, threshold: float) -> YOLODetector | None:
    global _detector
    if model_path is None:
        return None
    if _detector is None:
        try:
            _detector = YOLODetector(model_path, threshold)
        except ModelNotLoaded as exc:
            log.warning("YOLO no disponible: %s. Solo se usará template matching.", exc)
            return None
    return _detector
