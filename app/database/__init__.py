from app.database.session import Base, engine, get_db
from app.database.models import ResearchJob, Evidence, Document, DocumentAnalysis


def init_db():
    """Initialize database tables."""
    Base.metadata.create_all(bind=engine)


__all__ = ["Base", "engine", "get_db", "init_db", "ResearchJob", "Evidence", "Document", "DocumentAnalysis"]
