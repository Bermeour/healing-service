from __future__ import annotations

"""
Valida si un selector (XPath o CSS) existe en el DOM HTML dado.

Usado por el árbitro para verificar si el último selector sanado
sigue siendo válido antes de lanzar el scoring completo.

XPath  → lxml.etree (soporta el subset completo que genera xpath_builder)
CSS    → BeautifulSoup select()
coords → nunca validables contra DOM (dependen de coordenadas de pantalla)
"""

import logging
from functools import lru_cache

from bs4 import BeautifulSoup

log = logging.getLogger("healing.selector_validator")


def selector_exists(dom_html: str, selector: str, selector_type: str) -> bool:
    """
    Devuelve True si el selector encuentra al menos un elemento en el DOM.

    Args:
        dom_html:      HTML actual del browser (page_source)
        selector:      El selector a verificar
        selector_type: "xpath" | "css" | "coords"

    Returns:
        True si encuentra exactamente un elemento (o al menos uno para CSS).
        False si no encuentra nada, el tipo es coords, o ocurre cualquier error.
    """
    if not selector or not dom_html:
        return False

    if selector_type == "coords":
        # Las coordenadas no se pueden validar contra el DOM
        return False

    try:
        if selector_type == "xpath":
            return _check_xpath(dom_html, selector)
        if selector_type == "css":
            return _check_css(dom_html, selector)
    except Exception as exc:
        log.debug("Error validando selector '%s': %s", selector[:60], exc)

    return False


def _check_xpath(dom_html: str, xpath: str) -> bool:
    """Valida XPath usando lxml — soporta el subset completo que genera xpath_builder."""
    try:
        from lxml import etree  # lxml ya es dependencia vía beautifulsoup4

        # Parsea con recuperación de errores de HTML mal formado
        parser = etree.HTMLParser(recover=True)
        tree = etree.fromstring(dom_html.encode("utf-8", errors="replace"), parser)
        if tree is None:
            return False

        results = tree.xpath(xpath)
        found = bool(results)
        log.debug("XPath '%s' → %s (%d resultados)", xpath[:60], "FOUND" if found else "NOT FOUND", len(results) if isinstance(results, list) else 1)
        return found

    except Exception as exc:
        log.debug("lxml XPath falló ('%s'): %s", xpath[:60], exc)
        return False


def _check_css(dom_html: str, css: str) -> bool:
    """Valida selector CSS usando BeautifulSoup."""
    soup = BeautifulSoup(dom_html, "lxml")
    results = soup.select(css)
    found = len(results) > 0
    log.debug("CSS '%s' → %s (%d resultados)", css[:60], "FOUND" if found else "NOT FOUND", len(results))
    return found
