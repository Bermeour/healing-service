from __future__ import annotations

from app.engines.base import ElementBaseline
from app.engines.dom.text_similarity import (
    SEMANTIC_THRESHOLD_EXACT,
    SEMANTIC_THRESHOLD_PARTIAL,
    semantic_similarity,
)
from app.engines.dom.zones import ZoneHeuristics

_zone_heuristics = ZoneHeuristics()

# ── Perfiles de scoring ───────────────────────────────────────────────────────
#
# Cada perfil ajusta qué atributos pesan más según el tipo de aplicación.
# El cliente elige el perfil enviando "scoring_profile" en el HealRequest.
#
# default  → páginas estándar donde los IDs son estables
# siebel   → Siebel CRM: IDs generados por sesión, texto y aria son lo estable
# angular  → React / Angular / Vue: data-testid es el identificador canónico
# legacy   → Apps antiguas (Struts, JSF, VB): name es el atributo más estable

WEIGHT_PROFILES: dict[str, dict[str, int]] = {
    "default": {
        "data_testid":      50,
        "data_cy":          50,
        "data_qa":          50,
        "id":               40,
        "name":             35,
        "formcontrolname":  35,
        "text_exact":       35,
        "aria_label":       25,
        "title":            20,
        "placeholder":      18,
        "text_partial":     12,
        "class_exact":      12,
        "data_display":     10,
        "role":              8,
        "class_partial":     6,
        "type":              5,
        "parent_tag":        5,
        "tag_match":         5,
        "siblings_count":    3,
    },
    "siebel": {
        # Los IDs de Siebel son generados (s_sweui_1_R3C4_1) — casi inútiles.
        # El texto visible, aria-label, title y data-display son lo estable.
        "data_testid":      50,
        "text_exact":       45,
        "aria_label":       35,
        "title":            30,
        "data_display":     30,
        "name":             28,
        "placeholder":      22,
        "role":             15,
        "type":             12,
        "siblings_count":   10,
        "text_partial":     10,
        "parent_tag":        8,
        "class_partial":     5,
        "tag_match":         5,
        "id":                5,
        "class_exact":       3,
        "data_cy":           0,
        "data_qa":           0,
        "formcontrolname":   0,
    },
    "angular": {
        # React / Angular / Vue usan data-testid / data-cy como convención de testing.
        "data_testid":      70,
        "data_cy":          65,
        "data_qa":          65,
        "formcontrolname":  55,
        "aria_label":       30,
        "id":               25,
        "text_exact":       20,
        "name":             15,
        "role":             12,
        "type":              8,
        "placeholder":       8,
        "text_partial":      5,
        "class_exact":       5,
        "parent_tag":        3,
        "tag_match":         3,
        "siblings_count":    2,
        "class_partial":     2,
        "title":             2,
        "data_display":      0,
    },
    "legacy": {
        # Apps antiguas (Struts, JSF, AS400 web, VB.NET WebForms):
        # el atributo name es el identificador principal del servidor.
        "name":             45,
        "text_exact":       40,
        "id":               30,
        "data_testid":      25,
        "title":            22,
        "placeholder":      20,
        "aria_label":       15,
        "type":             12,
        "text_partial":     10,
        "siblings_count":    8,
        "parent_tag":        8,
        "class_exact":       5,
        "role":              5,
        "tag_match":         5,
        "class_partial":     3,
        "data_cy":           0,
        "data_qa":           0,
        "formcontrolname":   0,
        "data_display":      0,
    },
}

# Alias para compatibilidad con código existente que importe WEIGHTS directamente
WEIGHTS = WEIGHT_PROFILES["default"]

THRESHOLD = 60  # score mínimo para considerar un candidato válido


def score_candidate(
    baseline: ElementBaseline,
    candidate: dict,
    weights: dict[str, int] | None = None,
    use_semantic: bool = True,
) -> int:
    w = weights if weights is not None else WEIGHTS
    score = 0

    # data-testid — identificador de pruebas, altamente confiable
    if candidate.get("data_testid") and candidate["data_testid"] == _attr(baseline, "data_testid"):
        score += w["data_testid"]

    # data-cy / data-qa — convenciones de Cypress y QA
    if candidate.get("data_cy") and candidate["data_cy"] == _attr(baseline, "data_cy"):
        score += w.get("data_cy", 0)
    if candidate.get("data_qa") and candidate["data_qa"] == _attr(baseline, "data_qa"):
        score += w.get("data_qa", 0)

    # formcontrolname — Angular reactive forms
    if candidate.get("formcontrolname") and candidate["formcontrolname"] == _attr(baseline, "formcontrolname"):
        score += w.get("formcontrolname", 0)

    # id
    if baseline.id and candidate.get("id") == baseline.id:
        score += w["id"]

    # name
    if baseline.name and candidate.get("name") == baseline.name:
        score += w["name"]

    # aria-label
    if baseline.aria_label and candidate.get("aria_label") == baseline.aria_label:
        score += w["aria_label"]

    # title — estable en apps enterprise y Siebel
    if baseline.title and candidate.get("title") == baseline.title:
        score += w.get("title", 0)

    # data-display — usado en toolbars Siebel
    if baseline.data_display and candidate.get("data_display") == baseline.data_display:
        score += w.get("data_display", 0)

    # texto visible — primero intenta similaridad semántica, fallback a string
    cand_text = (candidate.get("text") or "").strip()
    if baseline.text and cand_text:
        if cand_text == baseline.text:
            score += w["text_exact"]
        elif use_semantic:
            sim = semantic_similarity(baseline.text, cand_text)
            if sim is not None:
                if sim >= SEMANTIC_THRESHOLD_EXACT:
                    score += w["text_exact"]
                elif sim >= SEMANTIC_THRESHOLD_PARTIAL:
                    score += int(w["text_partial"] * sim)
            elif len(baseline.text) >= 4 and baseline.text[:15] in cand_text:
                # fallback si el modelo no está disponible
                score += w["text_partial"]
        elif len(baseline.text) >= 4 and baseline.text[:15] in cand_text:
            score += w["text_partial"]

    # placeholder
    if baseline.placeholder and candidate.get("placeholder") == baseline.placeholder:
        score += w["placeholder"]

    # clases CSS
    cand_classes = set(candidate.get("classes", []))
    base_classes = set(baseline.classes)
    if base_classes:
        if base_classes == cand_classes:
            score += w["class_exact"]
        elif intersection := base_classes & cand_classes:
            ratio = len(intersection) / len(base_classes)
            score += int(w["class_partial"] * ratio)

    # etiqueta del nodo padre
    if baseline.parent_tag and candidate.get("parent_tag") == baseline.parent_tag:
        score += w["parent_tag"]

    # tag (siempre debería coincidir si se filtró bien, bonus menor)
    if candidate.get("tag") == baseline.tag:
        score += w["tag_match"]

    # cantidad de siblings — ayuda a distinguir en listas
    if baseline.siblings_count == candidate.get("siblings_count", -1):
        score += w["siblings_count"]

    # type (input[type=submit], etc.)
    if candidate.get("type") and candidate["type"] == _attr(baseline, "type"):
        score += w["type"]

    # role ARIA
    if candidate.get("role") and candidate["role"] == _attr(baseline, "role"):
        score += w["role"]

    # penalizaciones por zona (header/nav/footer/modal/close)
    node: object = candidate.get("node")  # Tag BS4 incluido por el extractor
    if node is not None:
        zone_delta, _ = _zone_heuristics.evaluate(node)  # type: ignore[arg-type]
        score += zone_delta

    return score


def _attr(baseline: ElementBaseline, key: str) -> str:
    """Accede a atributos extra que el baseline puede tener como metadatos."""
    return getattr(baseline, key, "") or ""
