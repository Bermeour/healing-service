import logging
import logging.handlers
from pathlib import Path


def setup_logging(log_level: str, log_file: Path) -> None:
    fmt = "%(asctime)s [%(levelname)-8s] %(name)s — %(message)s"
    date_fmt = "%Y-%m-%d %H:%M:%S"

    handlers: list[logging.Handler] = [logging.StreamHandler()]

    if log_file:
        handlers.append(
            logging.handlers.RotatingFileHandler(
                log_file,
                maxBytes=10 * 1024 * 1024,  # 10 MB
                backupCount=5,
                encoding="utf-8",
            )
        )

    logging.basicConfig(
        level=log_level.upper(),
        format=fmt,
        datefmt=date_fmt,
        handlers=handlers,
    )

    # Silencia loggers ruidosos de librerías externas
    for noisy in ("uvicorn.access", "sqlalchemy.engine"):
        logging.getLogger(noisy).setLevel(logging.WARNING)