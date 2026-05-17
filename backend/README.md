# FPI-CONNECT Backend

FastAPI backend application for Electronic Mail Management and Appointment Management System.

## Prerequisites

- Python 3.11+
- PostgreSQL database
- Redis (for rate limiting and Celery tasks)
- System dependencies (for OCR):
  - Tesseract OCR
  - poppler-utils

Some guides in this folder still mention `docker-compose exec …`. The project is intended to run **without Docker**; from the `backend` directory (virtualenv activated), use `python …`, `alembic …`, and PostgreSQL tools with the credentials from your `.env` (`DATABASE_URL`).

## Installation

### 1. Install Python Dependencies

```bash
pip install -r requirements.txt
```

### 2. Install System Dependencies

**On Windows:**
- Install Tesseract OCR from: https://github.com/UB-Mannheim/tesseract/wiki
- Install poppler-utils from: https://github.com/oschwartz10612/poppler-windows/releases

**On Linux (Ubuntu/Debian):**
```bash
sudo apt-get update
sudo apt-get install -y tesseract-ocr tesseract-ocr-fra tesseract-ocr-eng libtesseract-dev poppler-utils
```

**On macOS:**
```bash
brew install tesseract poppler
```

### 3. Set Up Environment Variables

Create a `.env` file in the root directory with the following variables:

```env
# Required
SECRET_KEY=your-secret-key-here-generate-a-random-string
DATABASE_URL=postgresql://username:password@localhost:5432/fpi_connect
# Note: If your password contains special characters like #, @, %, etc., 
# you must URL-encode them (e.g., # becomes %23, @ becomes %40, % becomes %25)

# Optional (with defaults)
REDIS_URL=redis://localhost:6379/0
CORS_ORIGINS=["http://localhost:3000","http://localhost:80"]
FRONTEND_URL=http://localhost:3000
BACKEND_URL=http://localhost:8000

# SMTP (optional)
SMTP_HOST=localhost
SMTP_PORT=587
SMTP_USER=your-smtp-user
SMTP_PASSWORD=your-smtp-password
SMTP_FROM=noreply@fpi-connect.local
SMTP_USE_TLS=true

# Storage (optional - defaults to local)
STORAGE_TYPE=local
STORAGE_PATH=./storage

# Microsoft Graph / Exchange (optional)
MICROSOFT_GRAPH_CLIENT_ID=your-client-id
MICROSOFT_GRAPH_CLIENT_SECRET=your-client-secret
MICROSOFT_GRAPH_TENANT_ID=your-tenant-id

# LDAP/AD (optional)
LDAP_SERVER=ldap://your-ldap-server
LDAP_BASE_DN=dc=example,dc=com

# Auth tokens / MFA
ACCESS_TOKEN_EXPIRE_MINUTES=30
REFRESH_TOKEN_EXPIRE_DAYS=14
REFRESH_TOKEN_COOKIE_NAME=refresh_token
# Set to false locally if you don't use HTTPS
REFRESH_TOKEN_SECURE=true
# lax | none | strict
REFRESH_TOKEN_SAMESITE=lax
MFA_SESSION_EXPIRE_MINUTES=10

# Google Calendar (optional)
GOOGLE_CLIENT_ID=your-google-client-id
GOOGLE_CLIENT_SECRET=your-google-client-secret
# Callback géré par l’API FastAPI (pas le frontend). Même valeur que dans Google Cloud → URI de redirection autorisés.
GOOGLE_REDIRECT_URI=http://localhost:8000/api/v1/auth/google/callback
```

### 4. Set Up Database

1. Create a PostgreSQL database:
```bash
createdb fpi_connect
```

2. Run database migrations:
```bash
alembic upgrade head
```

### 5. Create Admin User (Optional)

```bash
python -m app.scripts.create_admin
```

Or with custom credentials:
```bash
python -m app.scripts.create_admin --username admin --email admin@example.com --password yourpassword
```

## Running the Application

### Development Mode

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### Production Mode

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Before the first run (or after pulling migrations), ensure PostgreSQL and Redis are running locally, then:

```bash
python wait_for_db.py   # optional: waits until DATABASE_URL is reachable
alembic upgrade head
```

## Accessing the API

Once running, the API will be available at:
- **API Base URL**: http://localhost:8000
- **Interactive API Docs (Swagger)**: http://localhost:8000/docs
- **ReDoc Documentation**: http://localhost:8000/redoc
- **Health Check**: http://localhost:8000/health

## OpenAPI Export (YAML)

To generate a full OpenAPI file from the current FastAPI routes and schemas:

```bash
python scripts/export_openapi.py --out ../schema.yaml
```

This writes `schema.yaml` at the repository root.

## API Endpoints

- `/api/v1/auth` - Authentication endpoints
- `/api/v1/users` - User management
- `/api/v1/mail` - Mail management
- `/api/v1/appointments` - Appointment management
- `/api/v1/signatures` - Signature management
- `/api/v1/public` - Public endpoints

## Authentication Flow (MFA + Refresh Tokens)

- `/api/v1/auth/login`: password check, returns access token + refresh cookie, or `mfa_session_id` if MFA is enabled.
- `/api/v1/auth/mfa/verify`: submit `mfa_session_id` + code to receive tokens + refresh cookie.
- `/api/v1/auth/refresh`: reads HTTP-only refresh cookie, rotates it, returns a fresh access token.
- `/api/v1/auth/logout`: revokes the refresh session and clears the cookie.
- `/api/v1/auth/mfa/setup` → `/activate` → `/disable`: manage TOTP enrollment with Google Authenticator/FreeOTP.

## Google Calendar (OAuth)

1. [Google Cloud Console](https://console.cloud.google.com/) → APIs & Services → enable **Google Calendar API**.
2. **Credentials** → Create **OAuth client ID** (Application type: **Web application**).
3. Under **Authorized redirect URIs**, add the exact value of `GOOGLE_REDIRECT_URI` (e.g. `http://localhost:8000/api/v1/auth/google/callback` for local dev; in production use your public API URL with the same path).
4. Copy **Client ID** and **Client secret** into `.env` as `GOOGLE_CLIENT_ID` and `GOOGLE_CLIENT_SECRET`.
5. Each user connects from **Settings** in the app (`GET /api/v1/auth/google/start` then Google redirects to `GET /api/v1/auth/google/callback`). Confirmed appointments for that organizer are synced to their **primary** Google calendar when Google is configured and the user has completed OAuth.

## Running Celery Workers (Optional)

If you need background task processing (OCR, notifications):

1. Start Redis:
```bash
redis-server
```

2. Start Celery worker:
```bash
celery -A app.celery_app worker --loglevel=info
```

3. Start Celery beat (for scheduled tasks):
```bash
celery -A app.celery_app beat --loglevel=info
```

## Troubleshooting

### Database Connection Issues
- Ensure PostgreSQL is running
- Verify `DATABASE_URL` in `.env` is correct
- Check database credentials and permissions

### OCR Issues
- Verify Tesseract is installed and in PATH
- On Windows, you may need to set `TESSERACT_CMD` in `.env` to the full path
- Ensure language packs (fra, eng) are installed

### Redis Connection Issues
- Ensure Redis is running
- Verify `REDIS_URL` in `.env` matches your Redis configuration

