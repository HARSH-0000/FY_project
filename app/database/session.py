from pathlib import Path
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from app.core.config import settings
from app.core import logger

# Base class for models
Base = declarative_base()


def _create_db_engine():
    db_url = getattr(settings, "DATABASE_URL", None)
    if db_url and db_url.startswith("postgresql"):
        try:
            test_engine = create_engine(db_url, connect_args={"connect_timeout": 2})
            with test_engine.connect():
                logger.info("Connected to PostgreSQL database.")
                return test_engine
        except Exception as e:
            logger.warning(f"PostgreSQL connection failed ({e}). Falling back to SQLite.")

    # SQLite fallback
    base_dir = Path(__file__).resolve().parent.parent.parent
    data_dir = base_dir / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    sqlite_path = data_dir / "irium.db"
    sqlite_url = f"sqlite:///{sqlite_path}"
    logger.info(f"Using SQLite database at {sqlite_path}")
    return create_engine(sqlite_url, connect_args={"check_same_thread": False})


engine = _create_db_engine()
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def init_db():
    try:
        from app.database import models
        Base.metadata.create_all(bind=engine)
    except Exception as e:
        logger.warning(f"Could not auto-create database tables: {e}")


init_db()


def get_db():
    """Database session dependency."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

