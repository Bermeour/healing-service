from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Entorno
    app_env: str = "development"

    # Servidor
    host: str = "0.0.0.0"
    port: int = 8765
    workers: int = 1

    # Base de conocimiento
    db_url: str = "sqlite+aiosqlite:///./healing_knowledge.db"
    baselines_path: Path = Path("./baselines")

    # Umbrales de los motores
    dom_score_threshold: int = 60
    cv_confidence_threshold: float = 0.82

    # Auto-actualización de baseline tras sanación exitosa
    auto_update_baseline: bool = True
    auto_update_baseline_threshold: float = 0.90

    # Caché de resultados en memoria (TTL en segundos, 0 = desactivado)
    cache_ttl_seconds: int = 300

    # Similaridad semántica de texto (sentence-transformers)
    semantic_similarity_enabled: bool = True
    semantic_model: str = "all-MiniLM-L6-v2"

    # Logs
    log_level: str = "info"
    log_file: Path = Path("./logs/healing.log")

    @property
    def db_dialect(self) -> str:
        """
        Extrae el dialecto del DB_URL para que database.py ajuste el engine.

        sqlite+aiosqlite://...  → 'sqlite'
        mssql+aioodbc://...     → 'mssql'
        postgresql+asyncpg://.. → 'postgresql'
        """
        return self.db_url.split("+")[0].split(":")[0].lower()

    @property
    def is_dev(self) -> bool:
        return self.app_env == "development"

    def create_dirs(self) -> None:
        self.baselines_path.mkdir(parents=True, exist_ok=True)
        self.log_file.parent.mkdir(parents=True, exist_ok=True)


settings = Settings()