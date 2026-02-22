from __future__ import annotations

import os
from datetime import date, datetime
from typing import Generator

import sqlcipher3
from dotenv import load_dotenv
from sqlalchemy import (
    Column,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    create_engine,
    event,
    text,
)
from sqlalchemy.orm import DeclarativeBase, Session, relationship, sessionmaker

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///data/journal.db")
_DB_KEY = os.getenv("DB_ENCRYPTION_KEY")
if not _DB_KEY:
    raise RuntimeError("DB_ENCRYPTION_KEY is not set. Add it to your .env file.")

# Ensure data directory exists (relative path resolution)
_db_path = DATABASE_URL.replace("sqlite:///", "")
if not os.path.isabs(_db_path):
    _db_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), _db_path)
os.makedirs(os.path.dirname(_db_path), exist_ok=True)


def _make_sqlcipher_conn():
    conn = sqlcipher3.connect(_db_path, check_same_thread=False)
    conn.execute(f"PRAGMA key=\"{_DB_KEY}\"")
    return conn


engine = create_engine(
    "sqlite://",
    creator=_make_sqlcipher_conn,
    echo=False,
)


@event.listens_for(engine, "connect")
def set_sqlite_pragma(dbapi_conn, connection_record):
    cursor = dbapi_conn.cursor()
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(255), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=True)
    name = Column(String(255), nullable=False)
    google_id = Column(String(255), unique=True, nullable=True, index=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    entries = relationship("JournalEntry", back_populates="user", cascade="all, delete-orphan")


class ChatLog(Base):
    __tablename__ = "chat_logs"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    question = Column(Text, nullable=False)
    answer = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class AIInsight(Base):
    __tablename__ = "ai_insights"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    entry_date = Column(Date, nullable=False)
    insight_type = Column(String(50), nullable=False)  # "narrative" or "contextual"
    content = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class JournalEntry(Base):
    __tablename__ = "journal_entries"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    date = Column(Date, nullable=False)
    content = Column(Text, nullable=False, default="")
    word_count = Column(Integer, nullable=False, default=0)
    sentiment_score = Column(Float, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    user = relationship("User", back_populates="entries")

    __table_args__ = (UniqueConstraint("user_id", "date", name="uq_user_date"),)


def init_db() -> None:
    Base.metadata.create_all(bind=engine)


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
