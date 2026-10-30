from sqlalchemy import create_engine, Column, String, DateTime, JSON, Text
from sqlalchemy.orm import declarative_base, sessionmaker
from datetime import datetime, timezone
from app.core.config import settings

kwargs = {"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}
engine = create_engine(settings.database_url, connect_args=kwargs)
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)
Base = declarative_base()
class Analysis(Base):
    __tablename__ = "analyses"
    id = Column(String, primary_key=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    input_type = Column(String, nullable=False)
    verdict = Column(String, nullable=False)
    title = Column(Text, default="")
    payload = Column(JSON, nullable=False)
def init_db(): Base.metadata.create_all(engine)
