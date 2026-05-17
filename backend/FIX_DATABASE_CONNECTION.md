# Fix Database Connection Issue

## Problem
You can see data in the Docker database via psql, but the application running on localhost shows no tables/data.

## Root Cause
The application is connecting to a different database than the Docker one. This happens when:
1. Running the app locally (not in Docker)
2. The `.env` file has a different `DATABASE_URL` or doesn't exist
3. There's a local PostgreSQL instance on port 5432 that's different from Docker

## Solution

### Option 1: Use Docker Database from Local App (Recommended)

If you're running the app locally but want to use the Docker database:

1. Create/update `.env` file in the backend directory:
```env
SECRET_KEY=O8Mo9l8U2JxxJf_Oat_DX-dUpHLDjLYM3eLlwyDF8wE
DATABASE_URL=postgresql://fpi-admin:Fpi-c05b6q%23@localhost:5432/fpi_connect
```

Note: The password `Fpi-c05b6q#` is URL-encoded as `Fpi-c05b6q%23` (the `#` becomes `%23`)

2. Make sure Docker database is running:
```bash
docker-compose up -d db
```

3. Verify connection:
```bash
# From local machine
psql -h localhost -U fpi-admin -d fpi_connect
# Password: Fpi-c05b6q#
```

### Option 2: Run Everything in Docker (Recommended for Production)

Use Docker Compose to run everything:

```bash
docker-compose up -d
```

This ensures the backend connects to the correct database (`db` service).

### Option 3: Check for Conflicting PostgreSQL Instance

If you have a local PostgreSQL running on port 5432:

1. Check what's running on port 5432:
```bash
# Windows
netstat -ano | findstr :5432

# Or check Docker
docker ps | findstr 5432
```

2. If there's a local PostgreSQL, either:
   - Stop it and use Docker database
   - Or update your `.env` to point to the correct database

## Verify the Fix

1. Check which database the app is connecting to:
```bash
# In backend directory with venv activated
python -c "from app.core.config import settings; print(settings.DATABASE_URL)"
```

2. Test the connection:
```bash
# Should show tables and data
python check_db_connection.py
```

3. Check the API:
```bash
# Should return data
curl http://localhost:8000/api/v1/mail/
```

## Quick Fix Command

If you want to quickly point your local app to the Docker database, create/update `.env`:

```bash
# In backend directory
echo SECRET_KEY=O8Mo9l8U2JxxJf_Oat_DX-dUpHLDjLYM3eLlwyDF8wE > .env
echo DATABASE_URL=postgresql://fpi-admin:Fpi-c05b6q%23@localhost:5432/fpi_connect >> .env
```

Then restart your local application.

