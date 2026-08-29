# ============================================================
# NERRO - Auth Routes (routes/auth.py)
# Endpoints      : POST /api/auth/register, /api/auth/login, GET /api/auth/me
# Purpose        : User signup, login (JWT) and current-user profile.
# TEAM NOTE      : Uses an in-memory demo user list as fallback. Switch fully to
#                  the User DB table for production auth; get_current_user is the
#                  dependency every other route reuses for authorization.
# ============================================================
from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from passlib.context import CryptContext
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy.orm import Session

from app.core.database import get_db

router = APIRouter(prefix="/api/auth", tags=["Authentication"])

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")

# ---------------------------------------------------------------------------
# Pydantic Schemas
# ---------------------------------------------------------------------------


class RegisterRequest(BaseModel):
    username: str = Field(..., min_length=3, max_length=50)
    email: EmailStr
    password: str = Field(..., min_length=8)
    full_name: str = Field(..., min_length=1)
    role: str = Field(default="viewer", pattern="^(admin|field_officer|viewer)$")
    state: Optional[str] = None
    district: Optional[str] = None


class LoginRequest(BaseModel):
    username: str
    password: str


class UserResponse(BaseModel):
    id: str
    username: str
    email: str
    full_name: str
    role: str
    state: Optional[str] = None
    district: Optional[str] = None
    created_at: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse


class PasswordChange(BaseModel):
    current_password: str
    new_password: str = Field(..., min_length=8)


# ---------------------------------------------------------------------------
# In-memory demo store (replaced by DB in production)
# ---------------------------------------------------------------------------

_demo_users: list[dict] = [
    {
        "id": "usr_001",
        "username": "admin",
        "email": "admin@nerro.in",
        "full_name": "NERRO Administrator",
        "role": "admin",
        "state": "Assam",
        "district": "Kamrup Metro",
        "hashed_password": pwd_context.hash("admin123"),
        "created_at": "2025-01-15T08:00:00Z",
    },
    {
        "id": "usr_002",
        "username": "field_officer1",
        "email": "officer1@nerro.in",
        "full_name": "Rajesh Mech",
        "role": "field_officer",
        "state": "Arunachal Pradesh",
        "district": "Tawang",
        "hashed_password": pwd_context.hash("field123"),
        "created_at": "2025-02-10T09:30:00Z",
    },
]


# ---------------------------------------------------------------------------
# Helper – fake JWT (replace with real JWT in production)
# ---------------------------------------------------------------------------


def _create_access_token(user_id: str, expires_delta: Optional[timedelta] = None) -> str:
    expire = datetime.utcnow() + (expires_delta or timedelta(hours=24))
    payload = {"sub": user_id, "exp": expire, "iat": datetime.utcnow()}
    import base64, json
    return base64.urlsafe_b64encode(json.dumps(payload).encode()).decode()


def decode_token_payload(token: str) -> dict:
    import base64, json
    try:
        return json.loads(base64.urlsafe_b64decode(token))
    except Exception:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")


# ---------------------------------------------------------------------------
# Dependency
# ---------------------------------------------------------------------------


async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> dict:
    payload = decode_token_payload(token)
    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token payload")

    user = None
    try:
        from app.models.user import User
        user = db.query(User).filter(User.id == user_id).first()
    except Exception:
        pass

    if not user:
        user = next((u for u in _demo_users if u["id"] == user_id), None)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
    return user


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register(request: RegisterRequest, db: Session = Depends(get_db)):
    existing = next((u for u in _demo_users if u["username"] == request.username or u["email"] == request.email), None)
    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Username or email already registered")

    new_user = {
        "id": f"usr_{len(_demo_users)+1:03d}",
        "username": request.username,
        "email": request.email,
        "full_name": request.full_name,
        "role": request.role,
        "state": request.state,
        "district": request.district,
        "hashed_password": pwd_context.hash(request.password),
        "created_at": datetime.utcnow().isoformat() + "Z",
    }
    _demo_users.append(new_user)
    return UserResponse(**{k: v for k, v in new_user.items() if k != "hashed_password"})


@router.post("/login", response_model=TokenResponse)
async def login(request: LoginRequest, db: Session = Depends(get_db)):
    user = next((u for u in _demo_users if u["username"] == request.username), None)
    if not user or not pwd_context.verify(request.password, user["hashed_password"]):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Incorrect username or password")

    token = _create_access_token(user["id"])
    return TokenResponse(
        access_token=token,
        user=UserResponse(**{k: v for k, v in user.items() if k != "hashed_password"}),
    )


@router.get("/me", response_model=UserResponse)
async def get_me(current_user: dict = Depends(get_current_user)):
    return UserResponse(**{k: v for k, v in current_user.items() if k not in ("hashed_password",)})
