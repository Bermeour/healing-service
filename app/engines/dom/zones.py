from __future__ import annotations

from bs4 import Tag


class ZoneHeuristics:
    """
    Penaliza candidatos que están en zonas "trampa" del layout.

    Sin esto el scorer puede elegir el botón "X" de un modal,
    el logo del header, o un link de navegación en lugar del
    elemento de acción real.

    Uso:
        delta, reasons = ZoneHeuristics().evaluate(el)
        score += delta
    """

    def evaluate(self, el: Tag) -> tuple[int, list[str]]:
        score = 0
        reasons: list[str] = []

        # Dentro de header / nav → zona de navegación, no de contenido
        if self._has_ancestor_tag(el, {"header", "nav"}):
            score -= 20
            reasons.append("zona header/nav (-20)")

        # Dentro de footer
        if self._has_ancestor_tag(el, {"footer"}):
            score -= 10
            reasons.append("zona footer (-10)")

        # Clases típicas de botones trampa
        cls = self._classes(el)
        trap_classes = {
            "ghost", "secondary", "icon", "link",
            "close", "dismiss", "cancel",
            "navbar", "header", "topbar",
        }
        if cls & trap_classes:
            score -= 10
            reasons.append("clase tipo trampa (-10)")

        # Texto o aria-label que indica "cerrar / cancelar"
        aria = (el.get("aria-label") or "").lower()
        text = (el.get_text(strip=True) or "").lower()
        trap_words = {"cerrar", "close", "cancelar", "cancel", "dismiss", "x"}
        if trap_words & set(text.split()) or trap_words & set(aria.split()):
            score -= 10
            reasons.append("texto/aria tipo cerrar/cancel (-10)")

        # Dentro de modal / dialog / drawer (penalización suave, no siempre malo)
        if self._has_ancestor_class(el, {"modal", "dialog", "drawer"}):
            score -= 5
            reasons.append("zona modal/dialog/drawer (-5)")

        return score, reasons

    # ── helpers ──────────────────────────────────────────────────────────────

    def _has_ancestor_tag(self, el: Tag, tag_names: set[str]) -> bool:
        p = el
        while p is not None and getattr(p, "name", None) is not None:
            if p.name and p.name.lower() in tag_names:
                return True
            p = p.parent
        return False

    def _has_ancestor_class(self, el: Tag, class_names: set[str]) -> bool:
        p = el
        while p is not None and getattr(p, "name", None) is not None:
            if class_names & self._classes(p):
                return True
            p = p.parent
        return False

    def _classes(self, el: Tag) -> set[str]:
        return {c.lower() for c in (el.get("class") or [])}
