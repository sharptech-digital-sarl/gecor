from datetime import datetime, timedelta
from typing import Optional
import secrets
import hashlib
import bcrypt
from jose import JWTError, jwt
from fastapi import Depends, HTTPException, status, Request, Response
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session
import uuid

from app.core.config import settings
from app.core.database import get_db
from app.models.user import User

oauth2_scheme = OAuth2PasswordBearer(tokenUrl=f"{settings.API_V1_PREFIX}/auth/login", auto_error=False)


def normalize_login_password(raw: object) -> str:
    """Espaces / retours ligne accidentels (copier-coller depuis e-mail ou dialogue admin)."""
    return str(raw or "").strip()


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against its bcrypt hash (compatible with hashes created via passlib)."""
    if not hashed_password:
        return False
    pw = normalize_login_password(plain_password).encode("utf-8")
    digest = (
        hashed_password.strip().encode("utf-8")
        if isinstance(hashed_password, str)
        else hashed_password
    )
    try:
        return bcrypt.checkpw(pw, digest)
    except (ValueError, TypeError):
        return False


def get_password_hash(password: str) -> str:
    """Hash a password (bcrypt limits input to 72 bytes)."""
    if not isinstance(password, str):
        password = str(password)
    encoded = password.encode("utf-8")
    if len(encoded) > 72:
        raise ValueError("Password must be at most 72 bytes (bcrypt limit).")
    return bcrypt.hashpw(encoded, bcrypt.gensalt()).decode("utf-8")


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """Create a JWT access token"""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return encoded_jwt


def generate_refresh_token() -> str:
    """Generate a high-entropy refresh token"""
    return secrets.token_urlsafe(64)


def hash_token(token: str) -> str:
    """Hash a token with SHA-256 for DB storage"""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def refresh_token_expiry() -> datetime:
    """Compute refresh token expiry"""
    return datetime.utcnow() + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)


def _refresh_cookie_path() -> str:
    """Path large enough pour /auth/refresh, /auth/logout, etc. (même préfixe API)."""
    p = (settings.API_V1_PREFIX or "/api/v1").rstrip("/")
    return f"{p}/"


def set_refresh_cookie(response: Response, token: str) -> None:
    """Set the refresh token as a secure HTTP-only cookie"""
    response.set_cookie(
        key=settings.REFRESH_TOKEN_COOKIE_NAME,
        value=token,
        httponly=True,
        secure=settings.REFRESH_TOKEN_SECURE,
        samesite=settings.REFRESH_TOKEN_SAMESITE.lower(),
        max_age=settings.REFRESH_TOKEN_EXPIRE_DAYS * 24 * 60 * 60,
        domain=settings.REFRESH_TOKEN_COOKIE_DOMAIN,
        path=_refresh_cookie_path(),
    )


def clear_refresh_cookie(response: Response) -> None:
    """Remove refresh cookie on logout or invalidation"""
    response.delete_cookie(
        key=settings.REFRESH_TOKEN_COOKIE_NAME,
        domain=settings.REFRESH_TOKEN_COOKIE_DOMAIN,
        path=_refresh_cookie_path(),
    )


def verify_token(token: str) -> Optional[dict]:
    """Verify and decode a JWT token"""
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        return payload
    except jwt.ExpiredSignatureError:
        return None
    except jwt.JWTError as e:
        # Log the error for debugging (can be removed in production)
        import logging
        logger = logging.getLogger(__name__)
        logger.debug(f"JWT validation error: {e}")
        return None


async def get_current_user(
    request: Request,
    token: Optional[str] = Depends(oauth2_scheme),
    db: Session = Depends(get_db)
) -> User:
    """Get current authenticated user"""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    # Try to get token from query parameter as fallback (for img tags, etc.)
    if not token:
        token = request.query_params.get("token")
    
    if not token:
        raise credentials_exception
    
    payload = verify_token(token)
    if payload is None:
        raise credentials_exception
    
    user_id_str = payload.get("sub")
    if user_id_str is None:
        raise credentials_exception
    
    try:
        user_id: uuid.UUID = uuid.UUID(user_id_str)
    except (ValueError, TypeError):
        raise credentials_exception
    
    # Eagerly load roles relationship
    from sqlalchemy.orm import joinedload
    user = db.query(User).options(joinedload(User.roles)).filter(User.id == user_id).first()
    if user is None:
        raise credentials_exception
    
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is inactive"
        )
    
    return user


def require_role(*allowed_roles):
    """Dependency factory for role-based access control
    
    Args:
        *allowed_roles: UserRole enum values or role name strings
        
    Returns:
        Dependency function that checks if user has one of the allowed roles
    """
    from app.models.user import UserRole
    
    async def role_checker(current_user: User = Depends(get_current_user)) -> User:
        # Master role has access to everything
        if current_user.has_role("master"):
            return current_user
        
        # Convert allowed_roles to role name strings for comparison
        allowed_role_names = []
        for role in allowed_roles:
            if isinstance(role, UserRole):
                allowed_role_names.append(role.value.lower())
            else:
                allowed_role_names.append(str(role).lower())
        
        # Check if user has any of the allowed roles
        if not current_user.has_any_role(*allowed_role_names):
            # Format role names for error message
            role_display = [r.value if isinstance(r, UserRole) else str(r) for r in allowed_roles]
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access denied. Required roles: {', '.join(role_display)}"
            )
        return current_user
    return role_checker

