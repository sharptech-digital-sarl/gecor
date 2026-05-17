import os
from pathlib import Path
from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response, FileResponse
import yaml

from app.core.config import settings
from app.core.database import engine, Base
from app.api.v1 import (
    admin_console,
    auth,
    appointments,
    dashboard,
    deletion_requests,
    mail,
    notifications_api,
    public,
    roles,
    signatures,
    users,
)
from app.middleware.rate_limit import RateLimitMiddleware

SCHEMA_FILE = Path(__file__).resolve().parents[2] / "schema.yaml"

# Create database tables (skip during offline OpenAPI export)
if os.environ.get("OPENAPI_EXPORT") != "1":
    Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="GECOR API",
    description=(
        "GECOR — Gestion Electronique du Courrier et des Rendez-vous. "
        "API REST pour la gestion du courrier entrant/sortant/interne, l'agenda "
        "institutionnel, les visiteurs et l'administration on-premise."
    ),
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# Middleware order: first registered = inner, last = outer.
# CORSMiddleware must be outermost so every response (including 429 from rate limit) gets CORS headers.
cors_origins = settings.CORS_ORIGINS if isinstance(settings.CORS_ORIGINS, list) else ["http://localhost:3000"]
app.add_middleware(RateLimitMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    # Dev: accepte localhost / 127.0.0.1 / ::1 sur n'importe quel port (évite les blocages CORS si l’origine diffère légèrement)
    allow_origin_regex=r"https?://(localhost|127\.0\.0\.1|\[::1\])(:\d+)?$",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(auth.router, prefix="/api/v1/auth", tags=["Authentication"])
app.include_router(users.router, prefix="/api/v1/users", tags=["Users"])
app.include_router(roles.router, prefix="/api/v1/roles", tags=["Roles"])
app.include_router(mail.router, prefix="/api/v1/mail", tags=["Mail Management"])
app.include_router(dashboard.router, prefix="/api/v1/dashboard", tags=["Dashboard"])
app.include_router(appointments.router, prefix="/api/v1/appointments", tags=["Appointments"])
app.include_router(signatures.router, prefix="/api/v1/signatures", tags=["Signatures"])
app.include_router(public.router, prefix="/api/v1/public", tags=["Public"])
app.include_router(
    deletion_requests.router,
    prefix="/api/v1/deletion-requests",
    tags=["Deletion requests"],
)
app.include_router(notifications_api.router, prefix="/api/v1")
app.include_router(admin_console.router, prefix="/api/v1")


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return JSONResponse(content={"status": "healthy", "service": "gecor"})


@app.get("/")
async def root():
    """Root endpoint"""
    return {"message": "GECOR API", "version": app.version}


@app.get("/openapi.yaml", include_in_schema=False)
async def openapi_yaml():
    """OpenAPI schema as YAML."""
    content = yaml.dump(
        app.openapi(),
        sort_keys=False,
        allow_unicode=True,
        default_flow_style=False,
    )
    return Response(content=content, media_type="application/yaml; charset=utf-8")


@app.get("/schema", include_in_schema=False)
async def schema_as_yaml():
    """Serve static schema.yaml on /schema."""
    if not SCHEMA_FILE.is_file():
        raise HTTPException(
            status_code=404,
            detail="schema.yaml not found. Generate it with: python backend/scripts/export_openapi.py --out schema.yaml",
        )
    return FileResponse(
        path=str(SCHEMA_FILE),
        media_type="application/yaml; charset=utf-8",
        filename="schema.yaml",
    )

