# ============================================================
# NERRO - User Model (models/user.py)
# Purpose        : SQLAlchemy table for platform users (admin/field_officer/viewer).
# TEAM NOTE      : Auth endpoints currently use an in-memory demo list too; move
#                  fully to this table in production (get_current_user already
#                  prefers the DB row when present).
# ============================================================
import enum
from sqlalchemy import Column, Integer, String, Boolean, DateTime, Enum, func
from app.core.database import Base


class UserRole(str, enum.Enum):
    GOVERNMENT_OFFICIAL = "government_official"
    DISTRICT_ADMIN = "district_admin"
    LOGISTICS_OPERATOR = "logistics_operator"
    EMERGENCY_RESPONSE = "emergency_response"
    FIELD_OFFICER = "field_officer"


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(255), unique=True, index=True, nullable=False)
    full_name = Column(String(255), nullable=False)
    hashed_password = Column(String(255), nullable=False)
    role = Column(Enum(UserRole), nullable=False, default=UserRole.LOGISTICS_OPERATOR)
    district = Column(String(100))
    state = Column(String(100))
    phone = Column(String(20))
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
