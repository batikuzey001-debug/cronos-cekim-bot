import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from sqlalchemy.exc import OperationalError

from database.db import init_db

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        init_db()
    except OperationalError as e:
        logger.warning(
            "Veritabanına bağlanılamadı (DATABASE_URL kontrol edin): %s", e
        )
    except Exception as e:
        logger.warning("Veritabanı başlatılamadı: %s", e)
    yield


app = FastAPI(lifespan=lifespan)


@app.get("/")
def root():
    return {"message": "Bot çalışıyor", "status": "ok"}


@app.get("/health")
def health():
    """Railway / load balancer health check."""
    return {"status": "ok"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("admin.app:app", host="127.0.0.1", port=8001, reload=True)
