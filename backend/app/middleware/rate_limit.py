from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from app.core.request_ip import get_client_ip
from typing import Dict
import time


class RateLimiter:
    def __init__(self):
        self.requests: Dict[str, list] = {}

    def is_allowed(self, key: str, max_requests: int, window_seconds: int) -> bool:
        now = time.time()
        if key not in self.requests:
            self.requests[key] = []

        self.requests[key] = [
            req_time for req_time in self.requests[key] if now - req_time < window_seconds
        ]

        if len(self.requests[key]) >= max_requests:
            return False

        self.requests[key].append(now)
        return True


rate_limiter = RateLimiter()


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Rate limiting — doit rester *sous* CORSMiddleware pour que les réponses incluent les en-têtes CORS."""

    async def dispatch(self, request: Request, call_next):
        if request.url.path == "/health":
            return await call_next(request)

        client_ip = get_client_ip(request) or "unknown"
        path = request.url.path

        if path == "/api/v1/auth/password-reset-request/start" and request.method == "POST":
            if not rate_limiter.is_allowed(
                f"pwd_reset_start:{client_ip}", max_requests=10, window_seconds=3600
            ):
                return JSONResponse(
                    status_code=429,
                    content={"detail": "Too many password reset attempts. Try again later."},
                )
        elif path == "/api/v1/auth/password-reset-request/verify" and request.method == "POST":
            if not rate_limiter.is_allowed(
                f"pwd_reset_verify:{client_ip}", max_requests=30, window_seconds=3600
            ):
                return JSONResponse(
                    status_code=429,
                    content={"detail": "Too many verification attempts. Try again later."},
                )
        elif path.startswith("/api/v1/auth/login"):
            if not rate_limiter.is_allowed(f"login:{client_ip}", max_requests=5, window_seconds=300):
                return JSONResponse(
                    status_code=429,
                    content={"detail": "Too many login attempts. Please try again later."},
                )
        else:
            if not rate_limiter.is_allowed(f"api:{client_ip}", max_requests=100, window_seconds=60):
                return JSONResponse(
                    status_code=429,
                    content={"detail": "Rate limit exceeded. Please try again later."},
                )

        return await call_next(request)
