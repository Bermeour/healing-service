from __future__ import annotations

"""
El motor CV no tiene acceso directo al WebDriver (es un servicio REST),
por lo que no puede ejecutar elementFromPoint() directamente.

En su lugar, devuelve las coordenadas en formato "coords::x,y" y
el cliente (Python o Java) resuelve el XPath con este script JS:

    var el = document.elementFromPoint(x, y);
    // luego construye el XPath desde el nodo

Este módulo centraliza el formato y el script JS para que ambos
clientes usen exactamente la misma implementación.
"""

COORDS_PREFIX = "coords::"

# Script JS que el cliente inyecta en el browser para convertir
# coordenadas de pantalla en un XPath absoluto del nodo.
ELEMENT_FROM_POINT_SCRIPT = """
(function(x, y) {
    var el = document.elementFromPoint(x, y);
    if (!el) return null;
    var path = [];
    while (el && el.nodeType === 1) {
        var idx = 1;
        var sib = el.previousSibling;
        while (sib) {
            if (sib.nodeType === 1 && sib.tagName === el.tagName) idx++;
            sib = sib.previousSibling;
        }
        path.unshift(el.tagName.toLowerCase() + '[' + idx + ']');
        el = el.parentNode;
    }
    return '/' + path.join('/');
})(arguments[0], arguments[1]);
"""


def encode_coords(x: int, y: int) -> str:
    """Genera el selector de coordenadas que retorna el servicio."""
    return f"{COORDS_PREFIX}{x},{y}"


def decode_coords(selector: str) -> tuple[int, int]:
    """Parsea 'coords::320,480' → (320, 480)."""
    if not selector.startswith(COORDS_PREFIX):
        raise ValueError(f"El selector no es de tipo coords: {selector!r}")
    raw = selector[len(COORDS_PREFIX):]
    x_str, y_str = raw.split(",", 1)
    return int(x_str), int(y_str)


def is_coords_selector(selector: str) -> bool:
    return selector.startswith(COORDS_PREFIX)
