from datetime import datetime, timedelta
import hashlib
import hmac
import pyotp
import random
import secrets
import time
import uuid
from fastapi import APIRouter, Depends, HTTPException, status, Request, Response, Body
from fastapi.security import OAuth2PasswordRequestForm
from fastapi.responses import RedirectResponse
from typing import Optional
from sqlalchemy import func, or_
from sqlalchemy.orm import Session, joinedload
from urllib.parse import quote, urlencode

from app.core.database import get_db
from app.core.security import (
    verify_password,
    get_password_hash,
    normalize_login_password,
    create_access_token,
    get_current_user,
    require_role,
    generate_refresh_token,
    hash_token,
    refresh_token_expiry,
    set_refresh_cookie,
    clear_refresh_cookie,
)
from app.core.config import settings
from app.core.audit import audit_logger
from app.core.request_ip import get_client_ip
from app.models.role import Role
from app.models.user import User, UserRole
from app.models.password_reset_request import PasswordResetRequest, PasswordResetRequestStatus
from app.models.password_reset_challenge import PasswordResetChallenge, PasswordResetChallengeKind
from app.models.session_token import SessionToken
from app.models.mfa_session import MfaSession
from app.core.effective_permissions import get_effective_permissions
from app.services.google_calendar_service import google_calendar_service
from app.services.event_notifications import emit_in_app, user_ids_masters
from app.schemas.password_reset_request import (
    ForgotPasswordStartRequest,
    ForgotPasswordStartResponse,
    ForgotPasswordVerifyRequest,
    ForgotPasswordVerifyResponse,
)
from app.services.notification_service import notification_service
from app.schemas.user import (
    Token,
    User as UserSchema,
    UserMe,
    MeProfilePatch,
    NotificationSoundPrefs,
    LoginResponse,
    LoginRequest,
    LogoutRequest,
    RefreshTokenBody,
    MFASetupResponse,
    MFAActivateRequest,
    MFAVerifyRequest,
    ChangePasswordStartRequest,
    ChangePasswordStartResponse,
    ChangePasswordCompleteRequest,
)

router = APIRouter()

_CHALLENGE_TTL_MINUTES = 10
_GENERIC_START_MSG = "If an account exists for this email, follow the next steps to submit your request."
_GENERIC_VERIFY_MSG = "Your request has been recorded. An administrator has been notified."


def _hash_email_otp(code: str) -> str:
    return hmac.new(
        settings.SECRET_KEY.encode("utf-8"),
        f"pwdreset_email_otp:{code}".encode(),
        hashlib.sha256,
    ).hexdigest()


def _invalidate_open_challenges(db: Session, user_id: uuid.UUID) -> None:
    for row in (
        db.query(PasswordResetChallenge)
        .filter(
            PasswordResetChallenge.user_id == user_id,
            PasswordResetChallenge.consumed.is_(False),
        )
        .all()
    ):
        row.consumed = True
    db.commit()


def _invalidate_password_change_challenges(db: Session, user_id: uuid.UUID) -> None:
    for row in (
        db.query(PasswordResetChallenge)
        .filter(
            PasswordResetChallenge.user_id == user_id,
            PasswordResetChallenge.consumed.is_(False),
            PasswordResetChallenge.pending_password_hash.isnot(None),
        )
        .all()
    ):
        row.consumed = True
    db.commit()


def _notify_masters_new_reset_request(
    db: Session,
    email_norm: str,
    user: Optional[User],
    msg: Optional[str],
    request_id: uuid.UUID,
) -> None:
    master_ids = user_ids_masters(db)
    if not master_ids:
        return
    if user:
        account_line = f"Compte : {user.full_name} ({user.username})"
    else:
        account_line = "Aucun compte associé à cet e-mail"
    body_txt = f"E-mail indiqué : {email_norm}. {account_line}."
    if msg:
        body_txt += f" Message : {msg}"
    emit_in_app(
        db,
        master_ids,
        "Demande de réinitialisation mot de passe",
        body_txt,
        {"type": "password_reset_request", "request_id": str(request_id)},
    )


@router.post("/password-reset-request/start", response_model=ForgotPasswordStartResponse)
async def forgot_password_start(body: ForgotPasswordStartRequest, db: Session = Depends(get_db)):
    """Étape 1 : si compte actif, envoie un OTP par e-mail ou demande le TOTP (Google Authenticator)."""
    email_norm = body.email.strip().lower()
    msg = (body.message or "").strip() or None
    user = (
        db.query(User)
        .options(joinedload(User.roles))
        .filter(func.lower(User.email) == email_norm)
        .first()
    )
    if not user or not user.is_active:
        return ForgotPasswordStartResponse(flow="noop", message=_GENERIC_START_MSG)

    _invalidate_open_challenges(db, user.id)
    now = datetime.utcnow()
    expires = now + timedelta(minutes=_CHALLENGE_TTL_MINUTES)

    if user.is_mfa_enabled and user.mfa_secret:
        ch = PasswordResetChallenge(
            user_id=user.id,
            email_normalized=email_norm,
            kind=PasswordResetChallengeKind.TOTP.value,
            otp_code_hash=None,
            requester_message=msg,
            expires_at=expires,
            consumed=False,
        )
        db.add(ch)
        db.commit()
        db.refresh(ch)
        return ForgotPasswordStartResponse(
            flow="totp",
            message="Enter the 6-digit code from your authenticator app.",
            challenge_id=ch.id,
            expires_in_seconds=_CHALLENGE_TTL_MINUTES * 60,
        )

    host = (settings.SMTP_HOST or "").strip()
    if not host:
        raise HTTPException(
            status_code=503,
            detail="Email OTP is unavailable (SMTP not configured). Contact an administrator.",
        )

    code = f"{random.randint(0, 999999):06d}"
    ch = PasswordResetChallenge(
        user_id=user.id,
        email_normalized=email_norm,
        kind=PasswordResetChallengeKind.EMAIL_OTP.value,
        otp_code_hash=_hash_email_otp(code),
        requester_message=msg,
        expires_at=expires,
        consumed=False,
    )
    db.add(ch)
    db.commit()
    db.refresh(ch)

    loc = (user.preferred_locale or settings.DEFAULT_NOTIFICATION_LOCALE or "fr").lower()[:2]
    if loc == "en":
        subj = "Password reset verification code"
        plain = (
            f"Your verification code is: {code}\n\n"
            f"It expires in {_CHALLENGE_TTL_MINUTES} minutes.\n"
            "If you did not request this, ignore this email."
        )
    else:
        subj = "Code de vérification — mot de passe oublié"
        plain = (
            f"Votre code de vérification est : {code}\n\n"
            f"Il expire dans {_CHALLENGE_TTL_MINUTES} minutes.\n"
            "Si vous n'êtes pas à l'origine de cette demande, ignorez ce message."
        )

    sent = await notification_service.send_email(user.email, subj, plain)
    if not sent:
        ch.consumed = True
        db.commit()
        raise HTTPException(
            status_code=503,
            detail="Could not send verification email. Try again later or contact an administrator.",
        )

    return ForgotPasswordStartResponse(
        flow="email_otp",
        message="A verification code has been sent to your email address.",
        challenge_id=ch.id,
        expires_in_seconds=_CHALLENGE_TTL_MINUTES * 60,
    )


@router.post("/password-reset-request/verify", response_model=ForgotPasswordVerifyResponse)
def forgot_password_verify(body: ForgotPasswordVerifyRequest, db: Session = Depends(get_db)):
    """Étape 2 : après OTP / TOTP valide, crée la demande et notifie les masters."""
    now = datetime.utcnow()
    ch = (
        db.query(PasswordResetChallenge)
        .options(joinedload(PasswordResetChallenge.user))
        .filter(
            PasswordResetChallenge.id == body.challenge_id,
            PasswordResetChallenge.consumed.is_(False),
        )
        .first()
    )
    if not ch or ch.expires_at < now:
        raise HTTPException(status_code=400, detail="Invalid or expired challenge")

    user = ch.user
    if not user or not user.is_active:
        raise HTTPException(status_code=400, detail="Invalid challenge")

    code = body.code.strip()
    if ch.kind == PasswordResetChallengeKind.EMAIL_OTP.value:
        if not ch.otp_code_hash or _hash_email_otp(code) != ch.otp_code_hash:
            raise HTTPException(status_code=400, detail="Invalid verification code")
    elif ch.kind == PasswordResetChallengeKind.TOTP.value:
        if not user.mfa_secret:
            raise HTTPException(status_code=400, detail="MFA not configured for this account")
        totp = pyotp.TOTP(user.mfa_secret)
        if not totp.verify(code, valid_window=2):
            raise HTTPException(status_code=400, detail="Invalid authenticator code")
    else:
        raise HTTPException(status_code=400, detail="Invalid challenge type")

    ch.consumed = True
    db.add(ch)

    msg = ch.requester_message
    row = PasswordResetRequest(
        email_requested=ch.email_normalized,
        user_id=user.id,
        requester_message=msg,
        status=PasswordResetRequestStatus.PENDING.value,
        last_master_reminder_at=now,
    )
    db.add(row)
    db.commit()
    db.refresh(row)

    _notify_masters_new_reset_request(db, ch.email_normalized, user, msg, row.id)

    return ForgotPasswordVerifyResponse(message=_GENERIC_VERIFY_MSG)


_GOOGLE_OAUTH_STATE_TTL_SECONDS = 600


def _user_role_names(user: User) -> set[str]:
    return {role.name.lower() for role in user.roles}


def _mfa_required_for_user(user: User) -> bool:
    required_roles = {role.lower() for role in settings.MFA_REQUIRED_ROLES}
    if not required_roles:
        return False
    return bool(_user_role_names(user) & required_roles)


def _make_google_state(user_id: str, next_path: str = "/settings") -> str:
    ts = str(int(time.time()))
    nonce = secrets.token_hex(8)
    payload = f"{user_id}:{ts}:{nonce}:{next_path}"
    signature = hmac.new(
        settings.SECRET_KEY.encode("utf-8"),
        payload.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    return f"{payload}:{signature}"


def _parse_google_state(state: str) -> tuple[str, str]:
    raw = (state or "").strip()
    parts = raw.split(":")
    if len(parts) < 6:
        raise HTTPException(status_code=400, detail="Invalid OAuth state")

    user_id = parts[0]
    ts = parts[1]
    nonce = parts[2]
    next_path = ":".join(parts[3:-1]) or "/settings"
    provided_sig = parts[-1]
    payload = f"{user_id}:{ts}:{nonce}:{next_path}"
    expected_sig = hmac.new(
        settings.SECRET_KEY.encode("utf-8"),
        payload.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()

    if not hmac.compare_digest(expected_sig, provided_sig):
        raise HTTPException(status_code=400, detail="Invalid OAuth state signature")

    age_seconds = int(time.time()) - int(ts)
    if age_seconds > _GOOGLE_OAUTH_STATE_TTL_SECONDS:
        raise HTTPException(status_code=400, detail="Expired OAuth state")

    return user_id, next_path


def _google_callback_is_login_state(state: Optional[str]) -> bool:
    if not state:
        return False
    parts = state.strip().split(":")
    return len(parts) >= 5 and parts[0] == "login"


def _make_google_login_state(next_path: str) -> str:
    ts = str(int(time.time()))
    nonce = secrets.token_hex(8)
    safe_next = next_path if isinstance(next_path, str) and next_path.startswith("/") else "/app"
    payload = f"login:{ts}:{nonce}:{safe_next}"
    signature = hmac.new(
        settings.SECRET_KEY.encode("utf-8"),
        payload.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    return f"{payload}:{signature}"


def _parse_google_login_state(state: str) -> str:
    raw = (state or "").strip()
    parts = raw.split(":")
    if len(parts) < 5:
        raise HTTPException(status_code=400, detail="Invalid OAuth state")
    if parts[0] != "login":
        raise HTTPException(status_code=400, detail="Invalid OAuth state")
    ts = parts[1]
    nonce = parts[2]
    next_path = ":".join(parts[3:-1])
    provided_sig = parts[-1]
    payload = f"login:{ts}:{nonce}:{next_path}"
    expected_sig = hmac.new(
        settings.SECRET_KEY.encode("utf-8"),
        payload.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    if not hmac.compare_digest(expected_sig, provided_sig):
        raise HTTPException(status_code=400, detail="Invalid OAuth state signature")
    age_seconds = int(time.time()) - int(ts)
    if age_seconds > _GOOGLE_OAUTH_STATE_TTL_SECONDS:
        raise HTTPException(status_code=400, detail="Expired OAuth state")
    return next_path if next_path.startswith("/") else "/app"


def _complete_login_from_user_object(
    user: User,
    request: Request,
    response: Response,
    db: Session,
) -> LoginResponse:
    """Après identité vérifiée (mot de passe ou Google) : actif, MFA, jetons."""
    client_ip = get_client_ip(request)
    user_agent = request.headers.get("user-agent")

    if not user.is_active:
        audit_logger.log_login(user.id, False, client_ip, user_agent=user_agent)
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is inactive",
        )

    if _mfa_required_for_user(user) and not user.is_mfa_enabled:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="MFA must be enabled for your role before you can sign in.",
        )

    if user.is_mfa_enabled:
        mfa_session = MfaSession(
            user_id=user.id,
            expires_at=datetime.utcnow() + timedelta(minutes=settings.MFA_SESSION_EXPIRE_MINUTES),
        )
        db.add(mfa_session)
        db.commit()
        db.refresh(mfa_session)
        return LoginResponse(mfa_required=True, mfa_session_id=mfa_session.id)

    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": str(user.id), "role": user.role},
        expires_delta=access_token_expires,
    )

    refresh_token = generate_refresh_token()
    session_token = SessionToken(
        user_id=user.id,
        refresh_token_hash=hash_token(refresh_token),
        user_agent=user_agent,
        ip_address=client_ip,
        expires_at=refresh_token_expiry(),
    )

    user.last_login = datetime.utcnow()
    db.add(session_token)
    db.commit()
    db.refresh(session_token)

    audit_logger.log_login(user.id, True, client_ip, user_agent=user_agent)
    set_refresh_cookie(response, refresh_token)

    return LoginResponse(
        access_token=access_token,
        token_type="bearer",
        password_change_required=bool(getattr(user, "password_must_change", False)),
    )


async def _authenticate_user(
    username: str,
    password: str,
    request: Request,
    response: Response,
    db: Session
) -> LoginResponse:
    """Helper function to authenticate user and return login response"""
    client_ip = get_client_ip(request)
    user_agent = request.headers.get("user-agent")
    password = normalize_login_password(password)

    # Nom d'utilisateur ou e-mail (casse ignorée pour les deux).
    login_id = (username or "").strip()
    user = (
        db.query(User)
        .options(joinedload(User.roles))
        .filter(
            or_(
                func.lower(User.username) == login_id.lower(),
                func.lower(User.email) == login_id.lower(),
            )
        )
        .first()
    )
    
    if not user or not verify_password(password, user.hashed_password):
        if user:
            audit_logger.log_login(user.id, False, client_ip, user_agent=user_agent)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return _complete_login_from_user_object(user, request, response, db)


@router.post("/login", response_model=LoginResponse)
async def login(
    request: Request,
    response: Response,
    db: Session = Depends(get_db)
):
    """Authenticate user and return access token (or MFA challenge)
    
    Accepts both JSON (application/json) and form data (application/x-www-form-urlencoded).
    The ``username`` field may be the account username or the email address (email match is case-insensitive).
    For JSON, send: {"username": "...", "password": "..."}
    For form data, send: username=...&password=...
    """
    content_type = request.headers.get("content-type", "").lower()
    username = None
    password = None
    
    # Parse body based on Content-Type
    if "application/json" in content_type:
        # JSON format
        try:
            body = await request.json()
            login_data = LoginRequest(**body)
            username = login_data.username
            password = login_data.password
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Invalid JSON format: {str(e)}"
            )
    elif "application/x-www-form-urlencoded" in content_type or "multipart/form-data" in content_type:
        # Form data format
        try:
            form = await request.form()
            username = form.get("username")
            password = form.get("password")
            if not username or not password:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail="username and password are required in form data"
                )
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Invalid form data: {str(e)}"
            )
    else:
        # Try to detect format automatically
        try:
            # Try JSON first
            body = await request.json()
            login_data = LoginRequest(**body)
            username = login_data.username
            password = login_data.password
        except Exception:
            # Try form data
            try:
                form = await request.form()
                username = form.get("username")
                password = form.get("password")
            except Exception:
                pass
    
    if not username or not password:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="username and password are required. Send as JSON: {\"username\": \"...\", \"password\": \"...\"} or as form data (application/x-www-form-urlencoded)."
        )
    
    return await _authenticate_user(
        username=username,
        password=password,
        request=request,
        response=response,
        db=db
    )


@router.post("/refresh", response_model=Token)
async def refresh_token(
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
    body: RefreshTokenBody = Body(default_factory=RefreshTokenBody),
):
    """Rotate refresh token and issue a new access token (cookie httpOnly et/ou corps JSON)."""
    raw_refresh = request.cookies.get(settings.REFRESH_TOKEN_COOKIE_NAME) or (
        (body.refresh_token or "").strip() or None
    )
    if not raw_refresh:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token missing"
        )

    hashed = hash_token(raw_refresh)
    session_token = db.query(SessionToken).filter(
        SessionToken.refresh_token_hash == hashed,
        SessionToken.revoked_at.is_(None),
        SessionToken.expires_at > datetime.utcnow()
    ).first()

    if not session_token:
        clear_refresh_cookie(response)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token"
        )

    user = session_token.user
    if not user or not user.is_active:
        clear_refresh_cookie(response)
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is inactive"
        )

    access_token = create_access_token(
        data={"sub": str(user.id), "role": user.role},
        expires_delta=timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    )

    new_refresh = generate_refresh_token()
    session_token.refresh_token_hash = hash_token(new_refresh)
    session_token.expires_at = refresh_token_expiry()
    db.commit()

    set_refresh_cookie(response, new_refresh)
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "password_change_required": bool(getattr(user, "password_must_change", False)),
    }


@router.get("/google/start")
async def google_oauth_start(
    next_path: Optional[str] = "/settings",
    current_user: User = Depends(get_current_user),
):
    """Return Google OAuth authorization URL for calendar connection."""
    if not google_calendar_service.is_configured():
        raise HTTPException(status_code=400, detail="Google Calendar is not configured")
    safe_next = next_path if isinstance(next_path, str) and next_path.startswith("/") else "/settings"
    state = _make_google_state(str(current_user.id), safe_next)
    params = {
        "client_id": settings.GOOGLE_CLIENT_ID,
        "redirect_uri": settings.GOOGLE_REDIRECT_URI,
        "response_type": "code",
        "scope": " ".join(settings.GOOGLE_CALENDAR_SCOPES),
        "access_type": "offline",
        "include_granted_scopes": "true",
        "prompt": "consent",
        "state": state,
    }
    auth_url = f"https://accounts.google.com/o/oauth2/v2/auth?{urlencode(params)}"
    return {"auth_url": auth_url}


_GOOGLE_LOGIN_OAUTH_SCOPES = "openid email profile"


@router.get("/google/login/start")
async def google_login_oauth_start(next_path: Optional[str] = "/app"):
    """URL d’autorisation Google pour la connexion (même client OAuth que Calendar ; scopes identité uniquement)."""
    if not google_calendar_service.is_configured():
        raise HTTPException(status_code=400, detail="Google OAuth is not configured")
    safe_next = next_path if isinstance(next_path, str) and next_path.startswith("/") else "/app"
    state = _make_google_login_state(safe_next)
    params = {
        "client_id": settings.GOOGLE_CLIENT_ID,
        "redirect_uri": settings.GOOGLE_REDIRECT_URI,
        "response_type": "code",
        "scope": _GOOGLE_LOGIN_OAUTH_SCOPES,
        "access_type": "online",
        "prompt": "select_account",
        "state": state,
    }
    auth_url = f"https://accounts.google.com/o/oauth2/v2/auth?{urlencode(params)}"
    return {"auth_url": auth_url}


@router.get("/google/callback")
async def google_oauth_callback(
    request: Request,
    code: Optional[str] = None,
    state: Optional[str] = None,
    error: Optional[str] = None,
    db: Session = Depends(get_db),
):
    """Callback OAuth unique : connexion Google (state login:…) ou liaison Calendar (state = UUID utilisateur)."""
    fe = settings.FRONTEND_URL.rstrip("/")
    login_base = f"{fe}/login"
    cal_error = f"{fe}/app/settings?google_calendar=error"

    if error:
        if _google_callback_is_login_state(state):
            return RedirectResponse(url=f"{login_base}?google_login_error=oauth_denied")
        return RedirectResponse(url=cal_error)

    if not code or not state:
        if _google_callback_is_login_state(state):
            return RedirectResponse(url=f"{login_base}?google_login_error=oauth_failed")
        return RedirectResponse(url=cal_error)

    # --- Connexion Google (state préfixé par login) ---
    if _google_callback_is_login_state(state):
        try:
            login_next = _parse_google_login_state(state)
        except HTTPException:
            return RedirectResponse(url=f"{login_base}?google_login_error=oauth_failed")

        token_data = await google_calendar_service.exchange_code(code)
        if not token_data:
            return RedirectResponse(url=f"{login_base}?google_login_error=oauth_failed")

        access_token = token_data.get("access_token")
        if not access_token:
            return RedirectResponse(url=f"{login_base}?google_login_error=oauth_failed")

        google_email = await google_calendar_service.fetch_google_account_email(access_token)
        if not google_email:
            return RedirectResponse(url=f"{login_base}?google_login_error=oauth_failed")

        user = (
            db.query(User)
            .options(joinedload(User.roles))
            .filter(func.lower(User.email) == google_email.strip().lower())
            .first()
        )
        if not user:
            return RedirectResponse(url=f"{login_base}?google_login_error=no_account")

        client_ip = get_client_ip(request)
        user_agent = request.headers.get("user-agent")
        if not user.is_active:
            audit_logger.log_login(user.id, False, client_ip, user_agent=user_agent)
            return RedirectResponse(url=f"{login_base}?google_login_error=inactive")
        if _mfa_required_for_user(user) and not user.is_mfa_enabled:
            return RedirectResponse(url=f"{login_base}?google_login_error=mfa_policy")
        if user.is_mfa_enabled:
            mfa_session = MfaSession(
                user_id=user.id,
                expires_at=datetime.utcnow() + timedelta(minutes=settings.MFA_SESSION_EXPIRE_MINUTES),
            )
            db.add(mfa_session)
            db.commit()
            db.refresh(mfa_session)
            return RedirectResponse(
                url=f"{login_base}?google_mfa=1&mfa_session_id={mfa_session.id}"
            )

        # Toujours renvoyer vers /login?google_auth=1 : le SPA ne traite ce paramètre que sur la
        # page de connexion (refresh cookie → localStorage). Une redirection vers /app ferait
        # rejeter l’utilisateur (pas de jetons en localStorage) et perdre le query string.
        ok = RedirectResponse(
            url=f"{fe}/login?google_auth=1&next={quote(login_next, safe='')}"
        )
        _complete_login_from_user_object(user, request, ok, db)
        return ok

    # --- Liaison Google Calendar (utilisateur déjà connecté) ---
    try:
        user_id, next_path = _parse_google_state(state)
    except HTTPException:
        return RedirectResponse(url=cal_error)

    try:
        user_uuid = uuid.UUID(user_id)
    except ValueError:
        return RedirectResponse(url=cal_error)

    user = db.query(User).filter(User.id == user_uuid).first()
    if not user:
        return RedirectResponse(url=cal_error)

    token_data = await google_calendar_service.exchange_code(code)
    if not token_data:
        return RedirectResponse(url=cal_error)

    access_token = token_data.get("access_token")
    refresh_token = token_data.get("refresh_token")
    expires_in = int(token_data.get("expires_in", 3600))
    if not access_token:
        return RedirectResponse(url=cal_error)

    user.google_access_token = access_token
    user.google_access_token_expires_at = datetime.utcnow() + timedelta(seconds=expires_in)
    if refresh_token:
        user.google_refresh_token = refresh_token

    google_email = await google_calendar_service.fetch_google_account_email(access_token)
    if google_email:
        user.google_account_email = google_email

    db.add(user)
    db.commit()

    next_url = next_path if next_path.startswith("/") else "/app/settings"
    return RedirectResponse(url=f"{fe}{next_url}?google_calendar=connected")


@router.post("/google/disconnect")
async def google_disconnect(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Disconnect current user's Google Calendar account."""
    current_user.google_refresh_token = None
    current_user.google_access_token = None
    current_user.google_access_token_expires_at = None
    current_user.google_account_email = None
    db.add(current_user)
    db.commit()
    return {"message": "Google Calendar disconnected"}


@router.post("/logout")
async def logout(
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
    body: LogoutRequest = Body(default_factory=LogoutRequest),
):
    """Révoque la session de refresh (cookie et/ou corps) et supprime le cookie — sans JWT requis."""
    raw_refresh = request.cookies.get(settings.REFRESH_TOKEN_COOKIE_NAME) or (
        (body.refresh_token or "").strip() or None
    )
    if raw_refresh:
        hashed = hash_token(raw_refresh)
        session_token = db.query(SessionToken).filter(
            SessionToken.refresh_token_hash == hashed,
            SessionToken.revoked_at.is_(None),
        ).first()
        if session_token:
            session_token.revoked_at = datetime.utcnow()
            db.commit()

    clear_refresh_cookie(response)
    return {"message": "Logged out"}


@router.post("/mfa/setup", response_model=MFASetupResponse)
async def mfa_setup(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Start MFA enrollment and return provisioning data"""
    if current_user.is_mfa_enabled:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="MFA already enabled"
        )

    secret = pyotp.random_base32()
    current_user.mfa_temp_secret = secret
    db.commit()

    totp = pyotp.TOTP(secret)
    otpauth_url = totp.provisioning_uri(
        name=current_user.email or current_user.username,
        issuer_name=settings.PROJECT_NAME
    )
    return MFASetupResponse(secret=secret, otpauth_url=otpauth_url)


@router.post("/mfa/activate")
async def mfa_activate(
    payload: MFAActivateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Confirm MFA enrollment with the first TOTP code"""
    import logging
    logger = logging.getLogger(__name__)
    
    if current_user.is_mfa_enabled:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="MFA already enabled"
        )

    # Rafraîchir l'utilisateur depuis la DB pour s'assurer d'avoir le dernier secret
    db.refresh(current_user)
    
    if not current_user.mfa_temp_secret:
        logger.warning(f"No mfa_temp_secret for user {current_user.id} (username: {current_user.username})")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No MFA setup in progress. Please call /mfa/setup first."
        )

    # Créer l'objet TOTP avec le secret temporaire
    totp = pyotp.TOTP(current_user.mfa_temp_secret)
    
    # Vérifier le code avec une fenêtre de validité élargie pour le premier code
    # valid_window=2 permet ±60 secondes de tolérance
    is_valid = totp.verify(payload.code, valid_window=2)
    
    if not is_valid:
        # Générer le code attendu pour aider au debugging
        expected_code = totp.now()
        logger.warning(
            f"Invalid MFA code for user {current_user.id} (username: {current_user.username}). "
            f"Received: {payload.code}, Expected (current): {expected_code}"
        )
        
        # Message d'erreur plus détaillé pour aider au debugging
        error_message = (
            f"Invalid verification code. "
            f"Make sure you're using the code generated from the same secret returned by /mfa/setup. "
            f"Current expected code: {expected_code} (valid for ~30 seconds). "
            f"Tip: Use the test_mfa_helper.py script with the secret from /mfa/setup to generate the correct code."
        )
        
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=error_message
        )

    # Code valide, activer le MFA
    current_user.mfa_secret = current_user.mfa_temp_secret
    current_user.mfa_temp_secret = None
    current_user.is_mfa_enabled = True
    db.commit()
    db.refresh(current_user)
    
    logger.info(f"MFA enabled successfully for user {current_user.id} (username: {current_user.username})")
    return {"message": "MFA enabled successfully"}


@router.post("/mfa/disable")
async def mfa_disable(
    payload: MFAActivateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Disable MFA after validating a code"""
    if not current_user.is_mfa_enabled or not current_user.mfa_secret:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="MFA not enabled"
        )

    totp = pyotp.TOTP(current_user.mfa_secret)
    if not totp.verify(payload.code, valid_window=1):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid verification code"
        )

    current_user.is_mfa_enabled = False
    current_user.mfa_secret = None
    current_user.mfa_temp_secret = None
    db.commit()

    return {"message": "MFA disabled"}


@router.post("/mfa/verify", response_model=Token)
async def mfa_verify(
    payload: MFAVerifyRequest,
    request: Request,
    response: Response,
    db: Session = Depends(get_db)
):
    """Complete login by validating MFA and issuing tokens"""
    mfa_session = db.query(MfaSession).filter(
        MfaSession.id == payload.mfa_session_id,
        MfaSession.is_consumed.is_(False),
        MfaSession.expires_at > datetime.utcnow()
    ).first()

    if not mfa_session:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired MFA session"
        )

    user = mfa_session.user
    if not user or not user.mfa_secret:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User not eligible for MFA"
        )

    # Rafraîchir l'utilisateur pour s'assurer d'avoir le dernier secret
    db.refresh(user)
    
    import logging
    logger = logging.getLogger(__name__)
    
    totp = pyotp.TOTP(user.mfa_secret)
    
    # Augmenter la fenêtre de validité à 2 (±60 secondes) pour plus de tolérance
    is_valid = totp.verify(payload.code, valid_window=2)
    
    if not is_valid:
        expected_code = totp.now()
        logger.warning(
            f"Invalid MFA code for user {user.id} (username: {user.username}). "
            f"Received: {payload.code}, Expected (current): {expected_code}, "
            f"Session ID: {mfa_session.id}"
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid MFA code. Please check your authenticator app and try again."
        )
    
    logger.info(
        f"MFA verification successful for user {user.id} (username: {user.username}), "
        f"Session ID: {mfa_session.id}"
    )

    mfa_session.is_consumed = True

    access_token = create_access_token(
        data={"sub": str(user.id), "role": user.role},
        expires_delta=timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    )

    refresh_token = generate_refresh_token()
    session_token = SessionToken(
        user_id=user.id,
        refresh_token_hash=hash_token(refresh_token),
        user_agent=request.headers.get("user-agent"),
        ip_address=get_client_ip(request),
        expires_at=refresh_token_expiry(),
    )

    user.last_login = datetime.utcnow()
    db.add(session_token)
    db.commit()
    db.refresh(session_token)
    db.refresh(user)

    audit_logger.log_login(
        user.id,
        True,
        get_client_ip(request),
        user_agent=request.headers.get("user-agent"),
    )
    set_refresh_cookie(response, refresh_token)

    return {
        "access_token": access_token,
        "token_type": "bearer",
        "password_change_required": bool(getattr(user, "password_must_change", False)),
    }


@router.get("/me", response_model=UserMe)
async def read_users_me(current_user: User = Depends(get_current_user)):
    """Get current user information and effective permissions."""
    me = UserMe.model_validate(current_user)
    return me.model_copy(
        update={"permissions": sorted(get_effective_permissions(current_user))}
    )


@router.patch("/me", response_model=UserMe)
async def patch_users_me(
    body: MeProfilePatch,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Met à jour le profil minimal (ex. langue des e-mails, préférences sons)."""
    any_update = False
    if body.preferred_locale is not None:
        current_user.preferred_locale = body.preferred_locale
        any_update = True
    if body.notification_sound_prefs is not None:
        cur = dict(current_user.notification_sound_prefs or {})
        cur.update(body.notification_sound_prefs.model_dump(exclude_unset=True))
        validated = NotificationSoundPrefs.model_validate(cur)
        current_user.notification_sound_prefs = validated.model_dump()
        any_update = True
    if any_update:
        db.add(current_user)
        db.commit()
        db.refresh(current_user)
    me = UserMe.model_validate(current_user)
    return me.model_copy(
        update={"permissions": sorted(get_effective_permissions(current_user))}
    )


@router.post("/me/change-password/start", response_model=ChangePasswordStartResponse)
async def change_password_start(
    body: ChangePasswordStartRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Étape 1 : vérifie l’ancien mot de passe ; envoie OTP e-mail ou demande TOTP si MFA actif."""
    cur = normalize_login_password(body.current_password)
    if not verify_password(cur, current_user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Current password is incorrect",
        )
    np = body.new_password.strip()
    if len(np) < 8:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="new_password must be at least 8 characters",
        )
    if verify_password(np, current_user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="New password must be different from current password",
        )

    _invalidate_password_change_challenges(db, current_user.id)
    new_hash = get_password_hash(np)
    now = datetime.utcnow()
    expires = now + timedelta(minutes=_CHALLENGE_TTL_MINUTES)
    email_norm = (current_user.email or "").strip().lower()

    if current_user.is_mfa_enabled and current_user.mfa_secret:
        ch = PasswordResetChallenge(
            user_id=current_user.id,
            email_normalized=email_norm,
            kind=PasswordResetChallengeKind.PASSWORD_CHANGE_TOTP.value,
            otp_code_hash=None,
            requester_message=None,
            expires_at=expires,
            consumed=False,
            pending_password_hash=new_hash,
        )
        db.add(ch)
        db.commit()
        db.refresh(ch)
        return ChangePasswordStartResponse(
            flow="totp",
            challenge_id=ch.id,
            expires_in_seconds=_CHALLENGE_TTL_MINUTES * 60,
            message="Enter the 6-digit code from your authenticator app.",
        )

    host = (settings.SMTP_HOST or "").strip()
    if not host:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Email OTP is unavailable (SMTP not configured). Contact an administrator.",
        )

    code = f"{random.randint(0, 999999):06d}"
    ch = PasswordResetChallenge(
        user_id=current_user.id,
        email_normalized=email_norm,
        kind=PasswordResetChallengeKind.PASSWORD_CHANGE_EMAIL_OTP.value,
        otp_code_hash=_hash_email_otp(code),
        requester_message=None,
        expires_at=expires,
        consumed=False,
        pending_password_hash=new_hash,
    )
    db.add(ch)
    db.commit()
    db.refresh(ch)

    loc = (current_user.preferred_locale or settings.DEFAULT_NOTIFICATION_LOCALE or "fr").lower()[:2]
    if loc == "en":
        subj = "Password change verification code"
        plain = (
            f"Your verification code is: {code}\n\n"
            f"It expires in {_CHALLENGE_TTL_MINUTES} minutes.\n"
            "If you did not request a password change, ignore this email immediately."
        )
    else:
        subj = "Code de vérification — changement de mot de passe"
        plain = (
            f"Votre code de vérification est : {code}\n\n"
            f"Il expire dans {_CHALLENGE_TTL_MINUTES} minutes.\n"
            "Si vous n'êtes pas à l'origine de cette demande, ignorez ce message."
        )

    sent = await notification_service.send_email(current_user.email, subj, plain)
    if not sent:
        ch.consumed = True
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Could not send verification email. Try again later or contact an administrator.",
        )

    return ChangePasswordStartResponse(
        flow="email_otp",
        challenge_id=ch.id,
        expires_in_seconds=_CHALLENGE_TTL_MINUTES * 60,
        message="A verification code has been sent to your email address.",
    )


@router.post("/me/change-password/complete")
async def change_password_complete(
    body: ChangePasswordCompleteRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Étape 2 : valide OTP e-mail ou TOTP et applique le nouveau mot de passe."""
    now = datetime.utcnow()
    ch = (
        db.query(PasswordResetChallenge)
        .filter(
            PasswordResetChallenge.id == body.challenge_id,
            PasswordResetChallenge.user_id == current_user.id,
            PasswordResetChallenge.consumed.is_(False),
            PasswordResetChallenge.pending_password_hash.isnot(None),
        )
        .first()
    )
    if not ch or ch.expires_at < now:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired challenge",
        )

    code = body.code.strip()
    if ch.kind == PasswordResetChallengeKind.PASSWORD_CHANGE_EMAIL_OTP.value:
        if not ch.otp_code_hash or _hash_email_otp(code) != ch.otp_code_hash:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid verification code",
            )
    elif ch.kind == PasswordResetChallengeKind.PASSWORD_CHANGE_TOTP.value:
        if not current_user.mfa_secret:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="MFA not configured for this account",
            )
        totp = pyotp.TOTP(current_user.mfa_secret)
        if not totp.verify(code, valid_window=2):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid authenticator code",
            )
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid challenge type",
        )

    if not ch.pending_password_hash:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid challenge type",
        )
    ch.consumed = True
    current_user.hashed_password = ch.pending_password_hash
    current_user.password_must_change = False
    db.add(ch)
    db.add(current_user)
    db.commit()
    db.refresh(current_user)
    return {"message": "Password updated"}


@router.post("/register")
async def register(
    username: str,
    email: str,
    password: str,
    full_name: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.MASTER))
):
    """Register a new user (master only)"""
    # Check if user exists
    from sqlalchemy.orm import joinedload
    if db.query(User).options(joinedload(User.roles)).filter(User.username == username).first():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username already registered"
        )
    
    if db.query(User).options(joinedload(User.roles)).filter(User.email == email).first():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered"
        )
    
    guest_role = db.query(Role).filter(func.lower(Role.name) == "guest").first()
    if not guest_role:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Guest role is not configured in the database",
        )

    hashed_password = get_password_hash(password)
    new_user = User(
        username=username,
        email=email,
        hashed_password=hashed_password,
        full_name=full_name,
    )
    new_user.roles = [guest_role]

    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    
    return {"message": "User created successfully", "user_id": new_user.id}

