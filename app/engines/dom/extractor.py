from __future__ import annotations

from bs4 import BeautifulSoup, Tag


def parse_soup(html: str) -> BeautifulSoup:
    """Parsea el HTML y devuelve el objeto BeautifulSoup (para uso en anchors, filters, etc.)."""
    return BeautifulSoup(html, "lxml")


def parse_dom(html: str, tag: str) -> tuple[BeautifulSoup, list[dict]]:
    """
    Parsea el HTML y extrae todos los nodos del mismo tipo que el elemento
    buscado, devolviendo una lista de dicts con sus atributos relevantes.
    """
    soup = BeautifulSoup(html, "lxml")
    nodes = soup.find_all(tag)
    return soup, [_extract_attrs(node) for node in nodes if isinstance(node, Tag)]


def _extract_attrs(node: Tag) -> dict:
    """
    Extrae todos los atributos relevantes de un nodo BeautifulSoup.
    El dict resultante es el 'candidato' que el scorer compara contra el baseline.

    El campo 'node' guarda la referencia al Tag original para que xpath_builder
    pueda recorrer el árbol DOM hacia la raíz y construir el XPath final.
    """
    # BeautifulSoup puede devolver clases como string o como lista según el parser
    classes = node.get("class", [])
    if isinstance(classes, str):
        classes = classes.split()

    parent = node.parent
    parent_tag = parent.name if parent and isinstance(parent, Tag) else ""

    # siblings_count: cantidad de nodos hermanos del mismo tag.
    # Ayuda a distinguir elementos en tablas o listas donde otros atributos son iguales.
    siblings = [
        s for s in (node.parent.children if node.parent else [])
        if isinstance(s, Tag) and s.name == node.name and s is not node
    ]

    return {
        "node":           node,           # referencia al Tag (para xpath_builder)
        "tag":            node.name,
        "id":             node.get("id", ""),
        "name":           node.get("name", ""),
        "text":           node.get_text(strip=True),
        "classes":        list(classes),
        "aria_label":     node.get("aria-label", ""),
        "placeholder":    node.get("placeholder", ""),
        "parent_tag":     parent_tag,
        "siblings_count": len(siblings),
        "type":            node.get("type", ""),
        "value":           node.get("value", ""),
        "href":            node.get("href", ""),
        "role":            node.get("role", ""),
        "data_testid":     node.get("data-testid", ""),
        # atributos enterprise / multi-framework
        "data_cy":         node.get("data-cy", ""),
        "data_qa":         node.get("data-qa", ""),
        "formcontrolname": node.get("formcontrolname", ""),
        "title":           node.get("title", ""),
        "data_display":    node.get("data-display", ""),
    }
