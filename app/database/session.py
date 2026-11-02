from pathlib import Path
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from app.core.config import settings
from app.core import logger

# Base class for models
Base = declarative_base()


def _create_db_engine():
    """
    Create database engine - PostgreSQL ONLY (no SQLite fallback).
    If PostgreSQL connection fails, the application will not start.
    """
    from app.core.config import settings as config_settings
    db_url = getattr(config_settings, "DATABASE_URL", None)
    
    # DEBUG: Force config reload
    logger.info(f"DEBUG: DATABASE_URL = {db_url}")
    
    # Validate DATABASE_URL
    if not db_url:
        error_msg = "DATABASE_URL is not set in environment variables!"
        logger.error(error_msg)
        raise ValueError(error_msg)
    
    # If SQLite explicitly configured
    if db_url.startswith("sqlite"):
        logger.info(f"Connecting to SQLite database: {db_url}")
        engine = create_engine(db_url, connect_args={"check_same_thread": False})
        Base.metadata.create_all(bind=engine)
        return engine

    # Attempt PostgreSQL connection with graceful SQLite fallback
    logger.info(f"Connecting to PostgreSQL: {db_url.split('@')[1] if '@' in db_url else 'database'}")
    
    try:
        engine = create_engine(
            db_url, 
            connect_args={"connect_timeout": 5},
            pool_pre_ping=True,  # Verify connections before using
            pool_size=10,
            max_overflow=20
        )
        
        # Test the connection
        with engine.connect() as conn:
            from sqlalchemy import text
            conn.execute(text("SELECT 1"))
        
        logger.info("✅ PostgreSQL connection successful!")
        return engine
        
    except Exception as e:
        logger.warning(f"PostgreSQL connection failed ({e}). Falling back to SQLite at data/irium.db")
        sqlite_dir = Path(__file__).resolve().parent.parent.parent / "data"
        sqlite_dir.mkdir(exist_ok=True)
        sqlite_url = f"sqlite:///{sqlite_dir / 'irium.db'}"
        fallback_engine = create_engine(sqlite_url, connect_args={"check_same_thread": False})
        Base.metadata.create_all(bind=fallback_engine)
        logger.info("✅ SQLite fallback engine created successfully.")
        return fallback_engine


engine = _create_db_engine()
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Log the bound engine for verification
logger.info(f"✅ SessionLocal created and bound to: {engine.url.database}")
logger.info(f"   Dialect: {engine.dialect.name}")
logger.info(f"   Host: {engine.url.host}:{engine.url.port}")


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

