import logging
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

from config.settings import DATABASE_URL

logger = logging.getLogger(__name__)

engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,
    echo=False,
    connect_args={"connect_timeout": 10},
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    """FastAPI dependency için veritabanı oturumu."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """Tüm tabloları oluşturur. Bağlantı yoksa sessizce atlar (Railway'de DATABASE_URL sonradan eklenebilir)."""
    try:
        from admin import models  # noqa: F401
        Base.metadata.create_all(bind=engine)
    except Exception as e:
        logger.warning("init_db atlandi (veritabani ulasilir degil): %s", e)
