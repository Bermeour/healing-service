from __future__ import annotations

"""
Aprende qué atributos del baseline predicen mejor una sanación exitosa.

Algoritmo — "lift por atributo":
  Para cada atributo (id, name, aria_label...):
    1. Separa los eventos en dos grupos:
       - presente  : el baseline tenía ese atributo con valor
       - ausente   : el baseline no tenía ese atributo
    2. Calcula el "lift" = avg_conf(presente) / avg_conf(global)
       - lift > 1  → este atributo correlaciona con sanaciones más seguras
       - lift < 1  → no ayuda o confunde
    3. Nuevo peso = base_peso × (1 - α) + base_peso × lift × α
       donde α = LEARNING_RATE (qué tanto cede ante los datos)

Sin dependencias externas — solo numpy (ya incluido vía opencv).
scikit-learn se puede usar en una fase posterior para modelos más complejos
(Random Forest, gradiente, etc.) cuando haya más datos por proyecto.
"""

import logging

import numpy as np

from app.engines.dom.scorer import WEIGHT_PROFILES

log = logging.getLogger("healing.weight_learner")

# ── Hiperparámetros ───────────────────────────────────────────────────────────

MIN_SAMPLES = 10        # eventos mínimos para arrancar el aprendizaje
MIN_ATTR_SAMPLES = 3    # muestras mínimas por atributo para ajustarlo
LEARNING_RATE = 0.35    # cuánto ceden los pesos base ante los datos históricos
MAX_WEIGHT = 100        # techo para evitar pesos desbocados

# Atributos que el learner puede ajustar (deben existir en WEIGHT_PROFILES)
LEARNABLE_ATTRS = [
    "id", "name", "text_exact", "text_partial",
    "aria_label", "placeholder", "data_testid",
    "role", "type", "parent_tag", "class_exact",
]


# ── Función principal ─────────────────────────────────────────────────────────

def learn_weights(
    events: list[dict],
    base_profile: str = "default",
) -> tuple[dict[str, int], dict]:
    """
    Calcula nuevos pesos a partir del historial de eventos DOM.

    Args:
        events: lista de dicts con keys 'confidence' (float) y 'element_meta' (dict)
        base_profile: perfil base a partir del cual ajustar ('default', 'siebel', etc.)

    Returns:
        (learned_weights, stats) donde stats describe qué se ajustó y por qué
    """
    base_weights = dict(WEIGHT_PROFILES.get(base_profile, WEIGHT_PROFILES["default"]))

    if len(events) < MIN_SAMPLES:
        log.info(
            "Aprendizaje omitido: %d eventos < mínimo %d",
            len(events), MIN_SAMPLES,
        )
        return base_weights, {
            "skipped": True,
            "reason": f"eventos insuficientes: {len(events)} < {MIN_SAMPLES}",
            "sample_size": len(events),
        }

    confidences = np.array([e["confidence"] for e in events], dtype=float)
    global_mean = float(np.mean(confidences))

    learned: dict[str, int] = dict(base_weights)
    adjustments: dict[str, dict] = {}

    for attr in LEARNABLE_ATTRS:
        if attr not in base_weights:
            continue

        # Confianzas de eventos donde el baseline tenía este atributo con valor
        present_confs = np.array([
            e["confidence"] for e in events
            if _attr_is_present(e["element_meta"], attr)
        ], dtype=float)

        if len(present_confs) < MIN_ATTR_SAMPLES:
            continue  # no hay suficientes datos para este atributo

        present_mean = float(np.mean(present_confs))

        # Lift: ratio de confianza con este atributo vs sin él
        lift = present_mean / global_mean if global_mean > 0 else 1.0

        base = base_weights[attr]
        adjusted = base * (1 - LEARNING_RATE) + base * lift * LEARNING_RATE
        adjusted = int(max(1, min(MAX_WEIGHT, round(adjusted))))

        learned[attr] = adjusted
        adjustments[attr] = {
            "base": base,
            "learned": adjusted,
            "lift": round(lift, 3),
            "present_mean": round(present_mean, 3),
            "sample_size": int(len(present_confs)),
        }

        log.debug(
            "Atributo '%s': base=%d → aprendido=%d (lift=%.2f, n=%d)",
            attr, base, adjusted, lift, len(present_confs),
        )

    stats = {
        "skipped": False,
        "sample_size": len(events),
        "global_mean_confidence": round(global_mean, 3),
        "base_profile": base_profile,
        "adjustments": adjustments,
    }

    log.info(
        "Pesos aprendidos: %d atributos ajustados sobre %d eventos (conf_media=%.2f)",
        len(adjustments), len(events), global_mean,
    )

    return learned, stats


# ── Helpers ───────────────────────────────────────────────────────────────────

def _attr_is_present(meta: dict, attr: str) -> bool:
    """
    Determina si un atributo tiene valor útil en el element_meta del baseline.
    text_exact y text_partial usan el mismo campo 'text' del meta.
    """
    if attr in ("text_exact", "text_partial"):
        return bool(meta.get("text", "").strip())

    value = meta.get(attr)
    if isinstance(value, list):
        return len(value) > 0
    return bool(value)
