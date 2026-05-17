import os
from pathlib import Path
import json

from dotenv import load_dotenv
from pydantic_settings import BaseSettings
from pydantic import field_validator
from typing import List, Optional, Union

# backend/.env puis backend/app/.env (ce dernier surcharge pour le dev local).
# Sous Docker (RUNNING_IN_DOCKER=1), ne pas override l’environnement déjà fourni par Compose
# (sinon un app/.env copié dans l’image avec localhost écrase DATABASE_URL=@db:5432).
_backend_env = Path(__file__).resolve().parent.parent.parent / ".env"
_app_env = Path(__file__).resolve().parent.parent / ".env"
_override_dotenv = os.environ.get("OPENAPI_EXPORT") != "1" and os.environ.get("RUNNING_IN_DOCKER") != "1"
if _backend_env.is_file():
    # OPENAPI_EXPORT=1 : ne pas écraser les variables déjà fixées (ex. DATABASE_URL sqlite pour générer openapi.yaml)
    load_dotenv(_backend_env, override=_override_dotenv)
if _app_env.is_file():
    load_dotenv(_app_env, override=_override_dotenv)

# Mot de passe par défaut au bootstrap (create_admin) et pour les réinitialisations « politique »
# si PASSWORD_RESET_POLICY_DEFAULT n’est pas défini dans l’environnement — les deux doivent rester identiques.
DEFAULT_INITIAL_ADMIN_PASSWORD: str = "ChangeMoi@123!"


class Settings(BaseSettings):
    # Application
    PROJECT_NAME: str = "FPI-CONNECT"
    VERSION: str = "1.0.0"
    API_V1_PREFIX: str = "/api/v1"
    
    # Security
    SECRET_KEY: str
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 14
    REFRESH_TOKEN_COOKIE_NAME: str = "refresh_token"
    REFRESH_TOKEN_SECURE: bool = True
    REFRESH_TOKEN_SAMESITE: str = "lax"  # lax | none | strict
    REFRESH_TOKEN_COOKIE_DOMAIN: Optional[str] = None
    MFA_SESSION_EXPIRE_MINUTES: int = 10
    MFA_REQUIRED_ROLES: List[str] = []
    #: Mot de passe appliqué lors d'une réinitialisation « politique » (master / demande oubli).
    #: Par défaut = même valeur que create_admin ; en production, surcharger par une valeur forte (min. 8 caractères).
    PASSWORD_RESET_POLICY_DEFAULT: Optional[str] = DEFAULT_INITIAL_ADMIN_PASSWORD
    
    # Database
    DATABASE_URL: str
    
    # Redis
    REDIS_URL: str = "redis://localhost:6379/0"
    
    # CORS
    CORS_ORIGINS: List[str] = ["http://localhost:3000", "http://localhost:80"]
    
    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def parse_cors_origins(cls, v) -> List[str]:
        """Parse CORS_ORIGINS from JSON string or list"""
        if isinstance(v, str):
            try:
                # Try to parse as JSON array
                parsed = json.loads(v)
                if isinstance(parsed, list):
                    return [str(origin) for origin in parsed]
                # If it's a comma-separated string, split it
                origins = [origin.strip() for origin in v.split(",") if origin.strip()]
                return origins if origins else ["http://localhost:3000"]
            except (json.JSONDecodeError, ValueError):
                # If JSON parsing fails, treat as comma-separated string
                origins = [origin.strip() for origin in v.split(",") if origin.strip()]
                return origins if origins else ["http://localhost:3000"]
        elif isinstance(v, list):
            return [str(origin) for origin in v] if v else ["http://localhost:3000"]
        # Default fallback
        return ["http://localhost:3000", "http://localhost:80"]

    @field_validator("MFA_REQUIRED_ROLES", mode="before")
    @classmethod
    def parse_mfa_required_roles(cls, v) -> List[str]:
        if isinstance(v, str):
            try:
                parsed = json.loads(v)
                if isinstance(parsed, list):
                    return [str(role).strip().lower() for role in parsed if str(role).strip()]
            except (json.JSONDecodeError, ValueError):
                return [role.strip().lower() for role in v.split(",") if role.strip()]
        elif isinstance(v, list):
            return [str(role).strip().lower() for role in v if str(role).strip()]
        return []

    @field_validator("GOOGLE_CALENDAR_SCOPES", mode="before")
    @classmethod
    def parse_google_scopes(cls, v) -> List[str]:
        if isinstance(v, str):
            try:
                parsed = json.loads(v)
                if isinstance(parsed, list):
                    return [str(scope).strip() for scope in parsed if str(scope).strip()]
            except (json.JSONDecodeError, ValueError):
                return [scope.strip() for scope in v.split(",") if scope.strip()]
        elif isinstance(v, list):
            return [str(scope).strip() for scope in v if str(scope).strip()]
        return ["openid", "email", "https://www.googleapis.com/auth/calendar.events"]
    
    # SMTP
    SMTP_HOST: Optional[str] = None
    SMTP_PORT: int = 587
    SMTP_USER: Optional[str] = None
    SMTP_PASSWORD: Optional[str] = None
    SMTP_FROM: Optional[str] = None
    SMTP_USE_TLS: bool = True

    # E-mails transactionnels : langue par défaut si l’utilisateur n’a pas de préférence (fr | en).
    DEFAULT_NOTIFICATION_LOCALE: str = "fr"

    @field_validator("DEFAULT_NOTIFICATION_LOCALE", mode="after")
    @classmethod
    def normalize_default_notification_locale(cls, v: str) -> str:
        x = (v or "fr").strip().lower()[:8]
        return "en" if x.startswith("en") else "fr"
    
    # Storage
    STORAGE_TYPE: str = "local"  # local or s3
    STORAGE_PATH: str = "/app/storage"
    MINIO_ENDPOINT: Optional[str] = None
    MINIO_ACCESS_KEY: Optional[str] = None
    MINIO_SECRET_KEY: Optional[str] = None
    MINIO_BUCKET: str = "fpi-connect-files"
    
    # Outlook/Exchange
    MICROSOFT_GRAPH_CLIENT_ID: Optional[str] = None
    MICROSOFT_GRAPH_CLIENT_SECRET: Optional[str] = None
    MICROSOFT_GRAPH_TENANT_ID: Optional[str] = None
    EXCHANGE_SERVER_URL: Optional[str] = None
    EXCHANGE_USERNAME: Optional[str] = None
    EXCHANGE_PASSWORD: Optional[str] = None
    
    # Google Calendar
    GOOGLE_CLIENT_ID: Optional[str] = None
    GOOGLE_CLIENT_SECRET: Optional[str] = None
    GOOGLE_REDIRECT_URI: Optional[str] = None
    GOOGLE_CALENDAR_SCOPES: List[str] = [
        "openid",
        "email",
        "https://www.googleapis.com/auth/calendar.events",
    ]
    
    # OCR
    TESSERACT_CMD: str = "/usr/bin/tesseract"
    OCR_LANGUAGE: str = "fra+eng"
    
    # LDAP/AD
    LDAP_SERVER: Optional[str] = None
    LDAP_BASE_DN: Optional[str] = None
    LDAP_USER_DN: Optional[str] = None
    LDAP_GROUP_DN: Optional[str] = None
    
    # URLs
    FRONTEND_URL: str = "http://localhost:3000"
    BACKEND_URL: str = "http://localhost:8000"

    # Reverse proxy : lire X-Forwarded-For / X-Real-IP pour l’IP réelle (audit, sessions, rate limit).
    # Mettre false si l’API est joignable directement sans proxy (réduit le risque de spoofing des en-têtes).
    TRUST_FORWARDED_HEADERS: bool = True

    # Web Push (VAPID)
    VAPID_PUBLIC_KEY: str = os.getenv("VAPID_PUBLIC_KEY", "")
    VAPID_PRIVATE_KEY: str = os.getenv("VAPID_PRIVATE_KEY", "")
    VAPID_SUBJECT: str = os.getenv("VAPID_SUBJECT", "mailto:joelnyengele@gmail.com")
    
    class Config:
        # Look for .env in the backend root directory (parent of app/)
        env_file = None if os.environ.get("OPENAPI_EXPORT") == "1" else str(Path(__file__).parent.parent.parent / ".env")
        env_file_encoding = "utf-8"
        case_sensitive = True
    
    def __repr__(self) -> str:
        """Override repr to hide sensitive values"""
        # List of sensitive field names
        sensitive_fields = {
            'SECRET_KEY', 'SMTP_PASSWORD', 'DATABASE_URL', 
            'MICROSOFT_GRAPH_CLIENT_SECRET', 'GOOGLE_CLIENT_SECRET',
            'EXCHANGE_PASSWORD', 'MINIO_SECRET_KEY', 'LDAP_SERVER',
            'VAPID_PRIVATE_KEY', 'PASSWORD_RESET_POLICY_DEFAULT',
        }
        
        # Build a safe representation
        attrs = []
        for key, value in self.model_dump().items():
            if key in sensitive_fields:
                attrs.append(f"{key}='***HIDDEN***'")
            else:
                attrs.append(f"{key}={repr(value)}")
        
        return f"Settings({', '.join(attrs)})"


settings = Settings()

