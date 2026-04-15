from __future__ import annotations

from bs4 import Tag


def _is_inside(el: Tag, el_id: str) -> bool:
    """True si el elemento o algún ancestro tiene el id dado."""
    p: Tag | None = el
    while p is not None:
        if getattr(p, "attrs", None) and p.attrs.get("id") == el_id:
            return True
        p = p.parent  # type: ignore[assignment]
    return False


def _is_inside_class(el: Tag, class_expr: str) -> bool:
    """
    True si el elemento o algún ancestro tiene las clases indicadas.

    Formatos aceptados:
    - "nav-wrapper"              → ancestro con esa clase
    - "nav-wrapper header-zone"  → ancestro con AMBAS clases (AND)
    - "nav-wrapper,topbar"       → ancestro con cualquiera (OR entre grupos)
    """
    expr = (class_expr or "").strip()
    if not expr:
        return True

    or_groups = [g.strip() for g in expr.split(",") if g.strip()]

    def has_all(node: Tag, classes_str: str) -> bool:
        required = [c.strip().lower() for c in classes_str.split() if c.strip()]
        node_cls = {c.lower() for c in (node.get("class") or [])}
        return all(c in node_cls for c in required)

    p: Tag | None = el
    while p is not None:
        if getattr(p, "attrs", None) and p.get("class"):
            if any(has_all(p, g) for g in or_groups):
                return True
        p = p.parent  # type: ignore[assignment]
    return False


class CandidateFilter:
    """
    Aplica filtros duros antes del scoring para acotar el espacio de candidatos.

    Campos de contexto soportados:
    - exclude_ids      → descarta candidatos cuyo id esté en la lista
    - container_id     → solo acepta candidatos dentro de ese contenedor (por id)
    - container_class  → solo acepta candidatos dentro de ese contenedor (por clase)
    - form_id          → solo acepta candidatos dentro de ese formulario (por id)
    """

    def accept(
        self,
        candidate: dict,
        *,
        exclude_ids: list[str] | None = None,
        container_id: str | None = None,
        container_class: str | None = None,
        form_id: str | None = None,
    ) -> bool:
        node: Tag | None = candidate.get("node")
        if node is None:
            return True  # sin nodo no podemos filtrar, dejamos pasar

        # 1) exclusión por id
        if exclude_ids:
            cand_id = candidate.get("id", "")
            if cand_id and cand_id in exclude_ids:
                return False

        # 2) filtro por containerId
        if container_id:
            if not _is_inside(node, container_id):
                return False

        # 3) filtro por containerClass
        if container_class:
            if not _is_inside_class(node, container_class):
                return False

        # 4) filtro por formId (más específico que containerId)
        if form_id:
            if not _is_inside(node, form_id):
                return False

        return True
