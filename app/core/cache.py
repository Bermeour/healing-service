from __future__ import annotations

"""
Caché en memoria para resultados de healing recientes.

Evita reprocesar DOM y CV cuando el mismo selector roto se consulta
múltiples veces dentro de una misma ejecución de tests (patrón habitual
cuando varios tests comparten el mismo elemento).

La clave es (project, selector_value). El TTL es configurable vía
settings.cache_ttl_seconds (0 = caché desactivado).
"""

import logging
import time
from dataclasses import dataclass

from app.engines.base import EngineResult

log = logging.getLogger("healing.cache")


@dataclass
class _CacheEntry:
    result: EngineResult
    expires_at: float  # time.monotonic()


class HealingCache:
    """Caché LRU simple con TTL — thread-safe para asyncio (single-thread)."""

    def __init__(self, ttl_seconds: int = 300) -> None:
        self._ttl = ttl_seconds
        self._store: dict[tuple[str, str], _CacheEntry] = {}

    @property
    def enabled(self) -> bool:
        return self._ttl > 0

    def get(self, project: str, selector: str) -> EngineResult | None:
        if not self.enabled:
            return None

        key = (project, selector)
        entry = self._store.get(key)
        if entry is None:
            return None

        if time.monotonic() > entry.expires_at:
            del self._store[key]
            log.debug("Cache EXPIRED | project=%s selector=%.40s", project, selector)
            return None

        log.debug("Cache HIT | project=%s selector=%.40s", project, selector)
        return entry.result

    def set(self, project: str, selector: str, result: EngineResult) -> None:
        if not self.enabled:
            return

        self._store[(project, selector)] = _CacheEntry(
            result=result,
            expires_at=time.monotonic() + self._ttl,
        )
        log.debug("Cache SET | project=%s selector=%.40s ttl=%ds", project, selector, self._ttl)

    def invalidate(self, project: str, selector: str) -> None:
        """Elimina una entrada específica — llamar tras feedback negativo o update de baseline."""
        key = (project, selector)
        if key in self._store:
            del self._store[key]
            log.debug("Cache INVALIDATED | project=%s selector=%.40s", project, selector)

    def invalidate_project(self, project: str) -> int:
        """Elimina todas las entradas de un proyecto. Devuelve cuántas se eliminaron."""
        keys = [k for k in self._store if k[0] == project]
        for k in keys:
            del self._store[k]
        if keys:
            log.debug("Cache INVALIDATED project=%s (%d entradas)", project, len(keys))
        return len(keys)

    def stats(self) -> dict:
        now = time.monotonic()
        active = sum(1 for e in self._store.values() if e.expires_at > now)
        return {
            "enabled": self.enabled,
            "ttl_seconds": self._ttl,
            "total_entries": len(self._store),
            "active_entries": active,
        }


# Instancia global — vive mientras el proceso esté corriendo
_cache: HealingCache | None = None


def get_cache() -> HealingCache:
    global _cache
    if _cache is None:
        from app.core.config import settings
        _cache = HealingCache(ttl_seconds=settings.cache_ttl_seconds)
    return _cache
