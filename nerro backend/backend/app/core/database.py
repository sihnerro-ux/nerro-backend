# ============================================================
# NERRO - Database Setup (core/database.py)
# Purpose        : SQLAlchemy engine/session + PostGIS-ready base for PostgreSQL.
# TEAM NOTE      : Tables auto-create on startup (main.py lifespan). For schema
#                  changes use Alembic migrations. Connection string comes from
#                  config.py (DATABASE_URL environment variable).
# ============================================================
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from .config import get_settings

settings = get_settings()

engine = create_engine(settings.DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
