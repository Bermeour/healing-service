from __future__ import annotations

import unicodedata
from typing import TYPE_CHECKING

from bs4 import BeautifulSoup, Tag

if TYPE_CHECKING:
    pass

# Tags preferidos al buscar anclas por texto (más semánticos que div/span genérico)
_LABEL_TAGS = ["label", "span", "p", "h1", "h2", "h3", "h4", "strong", "small", "th", "td"]


def _normalize(s: str) -> str:
    s = s.strip().lower()
    s = " ".join(s.split())
    s = unicodedata.normalize("NFKD", s)
    return "".join(ch for ch in s if not unicodedata.combining(ch))


def _find_by_text(soup: BeautifulSoup, text: str) -> Tag | None:
    t = _normalize(text)
    if not t:
        return None
    for tag in _LABEL_TAGS:
        el = soup.find(tag, string=lambda s: bool(s and t in _normalize(s)))
        if el:
            return el
    node = soup.find(string=lambda s: bool(s and t in _normalize(s)))
    if node and getattr(node, "parent", None):
        return node.parent
    return None


def _find_by_id(soup: BeautifulSoup, el_id: str) -> Tag | None:
    if not el_id:
        return None
    return soup.find(attrs={"id": el_id})


def dom_distance(a: Tag, b: Tag) -> int:
    """
    Distancia entre dos nodos = suma de pasos hasta el ancestro común más cercano (LCA).
    Devuelve 999 si no tienen ancestro común (deberían siempre tenerlo en un doc válido).
    """
    def ancestors(node: Tag) -> list[Tag]:
        path = []
        current = node
        while current is not None and isinstance(current, Tag):
            path.append(current)
            current = current.parent  # type: ignore[assignment]
        return path

    anc_a = ancestors(a)
    anc_b = ancestors(b)
    set_b = {id(n): i for i, n in enumerate(anc_b)}

    for i, node in enumerate(anc_a):
        if id(node) in set_b:
            return i + set_b[id(node)]

    return 999


def _proximity_bonus(distance: int) -> int:
    if distance <= 3:
        return 30
    if distance <= 6:
        return 15
    if distance <= 10:
        return 5
    return 0


class AnchorResolver:
    """
    Localiza elementos de referencia (anchors) en el DOM y calcula
    cuánto bonus de proximidad aportan a un candidato.

    Anchors por defecto:
    - Elemento con id="user" o id="pass" (patrones de login clásicos)
    - El propio texto del baseline (si existe)

    Anchors personalizados (via request):
    - {"type": "id",   "value": "username_field", "weight": 40}
    - {"type": "text", "value": "Contraseña",     "weight": 30}
    - {"type": "css",  "value": "#form-login",    "weight": 20}
    """

    def resolve(
        self,
        soup: BeautifulSoup,
        baseline_text: str = "",
        custom_anchors: list[dict] | None = None,
    ) -> list[tuple[Tag, str, int]]:
        """
        Devuelve lista de (anchor_node, label, weight) para los anchors encontrados.
        """
        out: list[tuple[Tag, str, int]] = []

        # ── defaults ────────────────────────────────────────────────────────
        if baseline_text:
            el = _find_by_text(soup, baseline_text)
            if el:
                out.append((el, "baseline_text", 15))

        for default_id, weight in [("user", 30), ("pass", 30)]:
            el = _find_by_id(soup, default_id)
            if el:
                out.append((el, default_id, weight))

        # ── custom ──────────────────────────────────────────────────────────
        for i, anchor in enumerate(custom_anchors or []):
            a_type = (anchor.get("type") or "").lower()
            a_value = anchor.get("value") or ""
            a_weight = int(anchor.get("weight") or 30)
            label = f"custom_{i}:{a_type}"

            el: Tag | None = None
            if a_type == "id":
                el = _find_by_id(soup, str(a_value))
            elif a_type == "text":
                el = _find_by_text(soup, str(a_value))
            elif a_type == "css":
                try:
                    el = soup.select_one(str(a_value))
                except Exception:
                    pass

            if el:
                out.append((el, label, a_weight))

        return out

    def score_for_candidate(
        self,
        candidate_node: Tag,
        anchors: list[tuple[Tag, str, int]],
    ) -> int:
        """
        Calcula el bonus total de proximidad DOM para candidate_node
        respecto a todos los anchors encontrados.
        """
        total = 0
        for anchor_node, _label, weight in anchors:
            dist = dom_distance(anchor_node, candidate_node)
            bonus = _proximity_bonus(dist)
            if bonus > 0:
                total += int(bonus * (weight / 30))  # normaliza peso a base 30
        return total
