from __future__ import annotations

"""
Similaridad semántica de texto usando sentence-transformers local.

El modelo se carga una sola vez (singleton) la primera vez que se usa.
Si sentence-transformers no está instalado o falla la carga, todas las
llamadas devuelven None y el scorer cae de vuelta a la comparación de strings.

Modelo por defecto: all-MiniLM-L6-v2 (~80MB, muy rápido, buena calidad).
"""

import logging
from typing import Optional

import numpy as np

log = logging.getLogger("healing.text_similarity")

_model = None          # singleton del modelo cargado
_model_loaded = False  # True una vez que intentamos cargar (éxito o fallo)
_model_name: str = ""  # nombre del modelo que está cargado


def _load_model(model_name: str) -> None:
    global _model, _model_loaded, _model_name
    if _model_loaded:
        return

    _model_loaded = True
    try:
        from sentence_transformers import SentenceTransformer  # type: ignore
        log.info("Cargando modelo de similaridad semántica: %s", model_name)
        _model = SentenceTransformer(model_name)
        _model_name = model_name
        log.info("Modelo '%s' cargado correctamente", model_name)
    except ImportError:
        log.warning(
            "sentence-transformers no está instalado. "
            "La similaridad semántica usará comparación exacta de strings. "
            "Instala con: pip install sentence-transformers"
        )
    except Exception as exc:
        log.warning("Error al cargar modelo '%s': %s — usando comparación de strings", model_name, exc)


def semantic_similarity(text_a: str, text_b: str, model_name: str = "all-MiniLM-L6-v2") -> Optional[float]:
    """
    Calcula la similitud coseno entre dos textos usando embeddings locales.

    Args:
        text_a: Primer texto (ej: texto del baseline)
        text_b: Segundo texto (ej: texto del candidato en DOM actual)
        model_name: Modelo sentence-transformers a usar

    Returns:
        float [0.0 – 1.0] de similitud, o None si el modelo no está disponible.
        1.0 = textos idénticos semánticamente, 0.0 = sin relación.
    """
    if not text_a or not text_b:
        return None

    _load_model(model_name)

    if _model is None:
        return None

    try:
        embeddings = _model.encode([text_a, text_b], convert_to_numpy=True)
        # Similitud coseno manualmente para no depender de scipy
        a, b = embeddings[0], embeddings[1]
        norm_a = float(np.linalg.norm(a))
        norm_b = float(np.linalg.norm(b))
        if norm_a == 0 or norm_b == 0:
            return 0.0
        similarity = float(np.dot(a, b) / (norm_a * norm_b))
        # Clamp a [0, 1] — coseno puede dar valores ligeramente fuera por precisión float
        return max(0.0, min(1.0, similarity))
    except Exception as exc:
        log.debug("Error calculando similaridad semántica: %s", exc)
        return None


# Umbral a partir del cual consideramos que los textos son "el mismo" semánticamente
SEMANTIC_THRESHOLD_EXACT: float = 0.92   # casi idéntico → equivale a text_exact
SEMANTIC_THRESHOLD_PARTIAL: float = 0.75  # similar → equivale a text_partial
