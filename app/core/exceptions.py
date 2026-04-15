class HealingServiceError(Exception):
    """Base de todas las excepciones del servicio."""


class BaselineNotFound(HealingServiceError):
    def __init__(self, selector: str, project: str = ""):
        detail = f"proyecto='{project}', " if project else ""
        super().__init__(f"No hay baseline registrado para: {detail}selector='{selector}'")
        self.selector = selector
        self.project = project


class HealingFailed(HealingServiceError):
    def __init__(self, selector: str, dom_score: float = 0.0, cv_conf: float = 0.0):
        super().__init__(
            f"Ningún motor encontró el elemento '{selector}'. "
            f"DOM score={dom_score:.0f}, CV conf={cv_conf:.2f}"
        )
        self.selector = selector
        self.dom_score = dom_score
        self.cv_conf = cv_conf


class ModelNotLoaded(HealingServiceError):
    def __init__(self, model_path: str):
        super().__init__(f"No se pudo cargar el modelo CV desde: {model_path}")
        self.model_path = model_path


class InvalidBaseline(HealingServiceError):
    def __init__(self, reason: str):
        super().__init__(f"Baseline inválido: {reason}")


class AmbiguousMatch(HealingServiceError):
    """El motor encontró múltiples candidatos con el mismo score — no confiable."""
    def __init__(self, engine: str, count: int, score: float):
        super().__init__(
            f"Motor {engine}: {count} candidatos empatados con score={score:.0f}. "
            "No es posible determinar el elemento correcto."
        )
        self.engine = engine
        self.count = count
        self.score = score