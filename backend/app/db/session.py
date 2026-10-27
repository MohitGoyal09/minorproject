import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

# Default to SQLite for easy zero-setup local dev/testing; can be swapped to PostgreSQL via .env
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./accounting_system.db")

# For SQLite, check_same_thread=False allows FastAPI multi-threaded requests
connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}

engine = create_engine(DATABASE_URL, connect_args=connect_args, echo=False)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def get_db():
    """Dependency that yields a database session and ensures it closes safely."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
