# ============================================================
# NERRO - App Configuration (core/config.py)
# Purpose        : Central settings (env vars / .env) - database URL, CORS,
#                  JWT secret, API providers.
# TEAM NOTE      : Add any new API keys (ML model store, SMS, map provider)
#                  here with a default, then reference get_settings().KEY.
# ============================================================
from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    DATABASE_URL: str = "postgresql://nerro_user:nerro_password@localhost:5432/nerro"
    REDIS_URL: str = "redis://localhost:6379"
    SECRET_KEY: str = "nerro-super-secret-key-change-in-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 480
    OPENWEATHER_API_KEY: str = ""
    OPENROUTE_SERVICE_KEY: str = ""
    MAPTILER_KEY: str = ""
    CORS_ORIGINS: str = "http://localhost:5173,http://localhost:3000"
    DEMO_MODE: bool = True

    class Config:
        env_file = ".env"


@lru_cache
def get_settings() -> Settings:
    return Settings()
