import uvicorn
from app.core.config import settings

if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host=settings.host,
        port=settings.port,
        workers=settings.workers,   # configurado via WORKERS en .env
        reload=settings.is_dev,
        log_level=settings.log_level,
    )
