from __future__ import annotations

import re

from bs4 import Tag


# Atributos que se prueban para generar un XPath semántico, en orden de prioridad
_STABLE_ATTRS = [
    "data-testid",
    "data-cy",
    "data-qa",
    "id",
    "name",
    "formcontrolname",
    "aria-label",
    "placeholder",
    "title",
    "type",
    "role",
]


# ── Detección de IDs dinámicos (Siebel / jqGrid) ─────────────────────────────

def _is_stable_id(el_id: str) -> bool:
    """
    Devuelve False si el ID parece generado dinámicamente (Siebel, jqGrid, etc.)
    y no debe usarse como selector directo @id='...'.

    Patrones dinámicos detectados:
    - Empieza con dígito: "1_s_..."
    - Prefijo Siebel con segmentos numéricos: "s_1_2_130_0_fieldName"
    - Muchos guiones bajos con dígitos: 4+ dígitos y 3+ guiones bajos
    """
    if not el_id:
        return False
    s = str(el_id)
    if s[0].isdigit():
        return False
    if s.startswith("s_") and any(p in s for p in ("_l_", "_icon", "_ctl", "_sctrl_")):
        return False
    digits = sum(ch.isdigit() for ch in s)
    if digits >= 4 and s.count("_") >= 3:
        return False
    return True


def _id_stable_suffix(el_id: str) -> str | None:
    """
    Para IDs dinámicos extrae el sufijo semántico estable.
    Ejemplo: "s_1_2_130_0_Numero_identificacion" → "_Numero_identificacion"
    Devuelve None si no hay sufijo utilizable.
    """
    if not el_id:
        return None
    s = str(el_id)
    if "_" not in s:
        return None
    parts = [p for p in s.split("_") if p]
    if len(parts) >= 2:
        last = parts[-1]
        prev = parts[-2]
        if (last and prev
                and not last.isdigit() and not prev.isdigit()
                and len(prev) >= 3 and len(last) >= 3
                and prev.lower() not in {"s", "l", "ctl", "ctrl"}):
            return "_" + prev + "_" + last
        if last and len(last) >= 3 and not last.isdigit():
            return "_" + last
    return None


def build_xpath(node: Tag) -> str:
    """
    Genera el XPath más robusto posible para el nodo dado, en este orden:

    1. Atributo estable único (data-testid, id, name, aria-label, placeholder, type+text)
    2. XPath relativo corto anclado al ancestro con ID más cercano
    3. XPath relativo desde body usando solo índices mínimos (fallback)

    Evita XPaths absolutos desde /html que se rompen con cualquier cambio de layout.
    """
    # 1. Intentar generar por atributo estable único en el DOM completo
    xpath = _by_stable_attr(node)
    if xpath:
        return xpath

    # 2. XPath relativo anclado al ancestro con ID más cercano
    xpath = _anchored_to_ancestor(node)
    if xpath:
        return xpath

    # 3. Fallback: relativo desde body (nunca absoluto desde /html)
    return _relative_from_body(node)


# ── Estrategia 1: atributo estable ───────────────────────────────────────────

def _by_stable_attr(node: Tag) -> str | None:
    """Genera //tag[@attr='value'] si el atributo identifica de forma única al elemento."""
    root = _get_root(node)
    if root is None:
        return None

    tag = node.name

    for attr in _STABLE_ATTRS:
        value = node.get(attr, "")
        if not value:
            continue

        # Para 'id': verificar si es estable antes de usarlo directamente.
        # Si es dinámico (Siebel/jqGrid), intentar selector por sufijo estable.
        if attr == "id":
            if not _is_stable_id(value):
                suffix = _id_stable_suffix(value)
                if suffix:
                    n = len(suffix) - 1
                    candidate = (
                        f"//{tag}[@id and "
                        f"substring(@id, string-length(@id) - {n}) = {_esc(suffix)}]"
                    )
                    if _is_unique(root, candidate):
                        return candidate
                continue  # id dinámico sin sufijo útil: saltar

        # Texto visible combinado con type para inputs/buttons sin id
        if attr == "type" and tag in ("button", "input", "submit"):
            text = node.get_text(strip=True)
            if text:
                candidate = f"//{tag}[@type='{value}' and normalize-space()={_esc(text)}]"
                if _is_unique(root, candidate):
                    return candidate
            candidate = f"//{tag}[@type='{value}']"
            if _is_unique(root, candidate):
                return candidate
            continue

        candidate = f"//{tag}[@{attr}={_esc(value)}]"
        if _is_unique(root, candidate):
            return candidate

    # Texto visible exacto (para botones sin atributos estables)
    text = node.get_text(strip=True)
    if text and len(text) <= 50:
        candidate = f"//{tag}[normalize-space()={_esc(text)}]"
        if _is_unique(root, candidate):
            return candidate

    return None


# ── Estrategia 2: anclado al ancestro con ID ─────────────────────────────────

def _anchored_to_ancestor(node: Tag) -> str | None:
    """
    Busca el ancestro con ID más cercano y construye un XPath relativo desde él.
    Ejemplo: //*[@id='login-form']//button[1]
    """
    ancestor = node.parent
    path_parts: list[str] = []

    while ancestor and isinstance(ancestor, Tag) and ancestor.name not in ("[document]", None):
        anchor_id = ancestor.get("id", "")
        if anchor_id:
            # Construimos la ruta desde este ancestro hacia el nodo
            steps = _steps_from_ancestor(ancestor, node)
            if steps:
                return f"//*[@id={_esc(anchor_id)}]//{steps}"
            break
        ancestor = ancestor.parent  # type: ignore[assignment]

    return None


def _steps_from_ancestor(ancestor: Tag, node: Tag) -> str:
    """
    Construye los pasos de XPath desde ancestor hasta node usando índices mínimos.
    Devuelve cadena vacía si el nodo no es descendiente del ancestor.
    """
    # Construir el camino ascendente desde node hasta ancestor
    parts: list[str] = []
    current = node

    while current and current is not ancestor:
        if not isinstance(current, Tag) or current.name in ("[document]", None):
            return ""
        idx = _sibling_index(current)
        # Solo incluir índice si hay más de un hermano del mismo tag
        siblings_same_tag = _count_siblings(current)
        if siblings_same_tag > 1:
            parts.append(f"{current.name}[{idx}]")
        else:
            parts.append(current.name)
        current = current.parent  # type: ignore[assignment]

    if not parts:
        return ""

    parts.reverse()
    return "/".join(parts)


# ── Estrategia 3: relativo desde body ────────────────────────────────────────

def _relative_from_body(node: Tag) -> str:
    """
    Genera un XPath relativo desde //body, usando índices solo cuando hay ambigüedad.
    Es más corto y legible que el XPath absoluto desde /html.
    """
    parts: list[str] = []
    current = node

    while current and isinstance(current, Tag) and current.name not in ("[document]", "html", None):
        if current.name == "body":
            break
        siblings_same_tag = _count_siblings(current)
        if siblings_same_tag > 1:
            idx = _sibling_index(current)
            parts.append(f"{current.name}[{idx}]")
        else:
            parts.append(current.name)
        current = current.parent  # type: ignore[assignment]

    parts.reverse()
    return "//body/" + "/".join(parts) if parts else "//body"


# ── Helpers ───────────────────────────────────────────────────────────────────

def _get_root(node: Tag) -> Tag | None:
    """Sube hasta el nodo raíz del documento BeautifulSoup."""
    current = node
    while current.parent and isinstance(current.parent, Tag):
        current = current.parent  # type: ignore[assignment]
    return current


def _is_unique(root: Tag, xpath_expr: str) -> bool:
    """
    Comprueba si el XPath generado identifica exactamente un elemento en el DOM.
    Usa CSS aproximado porque BeautifulSoup no tiene motor XPath propio.
    """
    try:
        # Convertimos el XPath simple a una búsqueda BS4 equivalente
        results = _find_by_xpath_approx(root, xpath_expr)
        return len(results) == 1
    except Exception:
        return False


def _find_by_xpath_approx(root: Tag, xpath_expr: str) -> list[Tag]:
    """
    Aproximación de evaluación XPath usando BeautifulSoup find_all.
    Solo soporta las formas que genera este módulo.
    Acepta literales con comillas simples o dobles (generadas por _esc).
    concat() no se puede aproximar → retorna [] → no se marca como único.
    """
    # patrón genérico de literal: 'val' o "val"
    _LIT = r"""(?:'([^']*)'|"([^"]*)")"""

    # //tag[@attr=literal]
    m = re.match(rf"^//(\w+)\[@([\w\-:]+)={_LIT}\]$", xpath_expr)
    if m:
        tag, attr = m.group(1), m.group(2)
        value = m.group(3) if m.group(3) is not None else m.group(4)
        return root.find_all(tag, attrs={attr: value})

    # //tag[@attr=literal and normalize-space()=literal]
    m = re.match(rf"^//(\w+)\[@([\w\-:]+)={_LIT} and normalize-space\(\)={_LIT}\]$", xpath_expr)
    if m:
        tag, attr = m.group(1), m.group(2)
        val = m.group(3) if m.group(3) is not None else m.group(4)
        text = m.group(5) if m.group(5) is not None else m.group(6)
        candidates = root.find_all(tag, attrs={attr: val})
        return [c for c in candidates if c.get_text(strip=True) == text]

    # //tag[normalize-space()=literal]
    m = re.match(rf"^//(\w+)\[normalize-space\(\)={_LIT}\]$", xpath_expr)
    if m:
        tag = m.group(1)
        text = m.group(2) if m.group(2) is not None else m.group(3)
        return [c for c in root.find_all(tag) if c.get_text(strip=True) == text]

    return []


def _sibling_index(node: Tag) -> int:
    """Posición 1-based del nodo entre sus hermanos del mismo tag."""
    idx = 1
    for sibling in node.previous_siblings:
        if isinstance(sibling, Tag) and sibling.name == node.name:
            idx += 1
    return idx


def _count_siblings(node: Tag) -> int:
    """Total de hermanos con el mismo tag (incluyendo el propio nodo)."""
    if not node.parent or not isinstance(node.parent, Tag):
        return 1
    return sum(
        1 for s in node.parent.children
        if isinstance(s, Tag) and s.name == node.name
    )


def _esc(value: str) -> str:
    """
    Genera un literal XPath seguro para el valor dado.
    XPath 1.0 no soporta escape con backslash — usa concat() cuando hay comillas simples.
    """
    if value is None:
        return "''"
    if "'" not in value:
        return f"'{value}'"
    if '"' not in value:
        return f'"{value}"'
    # tiene ambas comillas: concat('O', "'", 'Brien')
    parts = value.split("'")
    return "concat(" + ", \"'\", ".join(f"'{p}'" for p in parts) + ")"
