# GECOR — Gestion Electronique du Courrier et des Rendez-vous

Plate-forme métier on-premise pour la gestion du courrier (entrant, sortant,
interne) et de l'agenda institutionnel. Conçue à l'origine pour l'**ARSP**,
elle reste générique : toute institution publique ou privée peut l'utiliser
pour tracer, archiver et piloter son flux documentaire et son agenda sans
dépendance cloud.

## Sommaire

- [Architecture](#architecture)
- [Démarrage rapide (Docker Compose)](#démarrage-rapide-docker-compose)
- [Démarrage rapide (sans Docker)](#démarrage-rapide-sans-docker)
- [Comptes et premier login](#comptes-et-premier-login)
- [Scripts utiles](#scripts-utiles)
- [Tests et qualité](#tests-et-qualité)
- [Documentation détaillée](#documentation-détaillée)
- [Structure du dépôt](#structure-du-dépôt)

## Architecture

```
            ┌─────────────────────┐
            │  Frontend React     │  Vite + MUI + TanStack Query
            │  (port 3000/3001)   │  i18n FR/EN, Web Push, SSE
            └─────────┬───────────┘
                      │ HTTPS / HTTP (Nginx reverse-proxy en prod)
                      ▼
            ┌─────────────────────┐
            │  Backend FastAPI    │  REST /api/v1, OAuth Google, MFA TOTP
            │  (port 8000/8001)   │  Audit, RBAC, workflows configurables
            └────┬────────┬───────┘
                 │        │
        ┌────────▼──┐   ┌─▼──────────┐   ┌──────────────┐
        │PostgreSQL │   │  Redis     │   │ Stockage     │
        │  15+      │   │  (Celery,  │   │ local / S3   │
        │           │   │  SSE, RL)  │   │ (MinIO)      │
        └───────────┘   └──┬─────────┘   └──────────────┘
                           │
                       ┌───▼──────────┐
                       │ Celery worker│  OCR (Tesseract), rappels RDV,
                       │ + beat       │  SLA, escalades, notifications
                       └──────────────┘
```

Stack :

- **Backend** : Python 3.12, FastAPI, SQLAlchemy 2, Alembic, Celery, pydantic-settings.
- **Frontend** : React 18, TypeScript, Vite, MUI 5, TanStack Query 5, react-router 6.
- **Base de données** : PostgreSQL 15+ (UUID, JSONB, recherche plein-texte).
- **Asynchrone** : Celery + Redis (rappels RDV, OCR, escalades, rappels mots de passe).
- **Sécurité** : Argon2 + bcrypt, JWT (access) + cookie refresh HttpOnly, MFA TOTP,
  rate-limit Redis, audit complet en base.

Pour l'architecture détaillée voir [`docs/architecture.md`](docs/architecture.md).

## Démarrage rapide (Docker Compose)

```bash
# 1. Copier les variables d'environnement
cp .env.example .env

# 2. Editer .env et au minimum :
#    - SECRET_KEY (chaîne aléatoire longue)
#    - POSTGRES_PASSWORD / DATABASE_URL (cohérents)

# 3. Lancer la stack complète (db, redis, backend, celery worker + beat, frontend)
docker compose up -d --build

# 4. Créer le compte master initial
docker compose exec backend python -m app.scripts.create_admin \
  --username admin --email admin@gecor.local
```

Vérifications :

- API : <http://localhost:8001/health> doit renvoyer `{"status":"healthy", ...}`
- Docs API : <http://localhost:8001/docs>
- Frontend : <http://localhost:3001>

## Démarrage rapide (sans Docker)

Prérequis : Python 3.12, Node.js 18+, PostgreSQL 15+, Redis, Tesseract OCR
(`tesseract-ocr-fra tesseract-ocr-eng poppler-utils`).

```bash
# Backend
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env  # ajuster DATABASE_URL, SECRET_KEY
python wait_for_db.py
alembic upgrade head
python -m app.scripts.create_admin
uvicorn app.main:app --reload --port 8000

# Frontend (autre terminal)
cd frontend
npm install
cp .env.example .env  # VITE_API_URL=http://localhost:8000/api/v1
npm run dev

# Celery (autre terminal, optionnel mais recommandé)
cd backend && source .venv/bin/activate
celery -A app.celery_app worker --loglevel=info
celery -A app.celery_app beat --loglevel=info
```

## Comptes et premier login

Le script `create_admin` crée un compte **master** (super-administrateur) avec
le mot de passe par défaut `ChangeMoi@123!`. Il **doit** être changé au premier
login (le backend marque `password_must_change=True`).

Rôles fournis par défaut : `master`, `director`, `secretary`, `analyst`,
`receptionist`, `archivist`, `guest`. Permissions granulaires définies dans
[`backend/app/core/permissions.py`](backend/app/core/permissions.py).

## Scripts utiles

| Commande                                                       | Effet                                                  |
| -------------------------------------------------------------- | ------------------------------------------------------ |
| `bash scripts/backup_postgres.sh`                              | Dump compressé de la base + rotation 30 jours.         |
| `bash scripts/restore_postgres.sh <fichier.sql.gz>`            | Restaure un dump pg compressé.                         |
| `python backend/scripts/export_openapi.py --out schema.yaml`   | Exporte le schéma OpenAPI à la racine.                 |
| `python -m app.scripts.create_admin --ensure`                  | Crée ou réinitialise le master au mot de passe défaut. |
| `docker compose logs -f backend`                               | Suivre les logs de l'API.                              |

## Tests et qualité

```bash
cd backend
pip install -r requirements-dev.txt
pytest                     # tests unitaires + smoke
ruff check .               # lint
black --check .            # format
```

Pour la qualité frontend :

```bash
cd frontend
npm run lint
npm run build
```

## Documentation détaillée

- [`docs/architecture.md`](docs/architecture.md) — modules, modèles, flux.
- [`docs/installation.md`](docs/installation.md) — installation dev et production.
- [`docs/maintenance.md`](docs/maintenance.md) — backup, restauration, mises à jour.
- [`docs/user-guide-fr.md`](docs/user-guide-fr.md) — guide utilisateur final.
- [`docs/recette.md`](docs/recette.md) — critères d'acceptation et plan de recette.
- [`backend/AGENTS.md`](backend/AGENTS.md) — cahier des charges Codex.

## Structure du dépôt

```
.
├── backend/                  # API FastAPI + Celery
│   ├── app/
│   │   ├── api/v1/           # Routers REST (auth, mail, appointments, …)
│   │   ├── core/             # config, sécurité, audit, permissions, DB
│   │   ├── models/           # ORM SQLAlchemy
│   │   ├── schemas/          # Modèles Pydantic
│   │   ├── services/         # Logique métier (workflow, OCR, notifications, …)
│   │   ├── tasks/            # Tâches Celery (OCR, rappels)
│   │   └── scripts/          # Scripts CLI (create_admin, …)
│   ├── alembic/              # Migrations
│   ├── dev-tools/            # Scripts ponctuels / debug (non livrés en prod)
│   ├── docs/troubleshooting/ # Mémos de dépannage
│   └── tests/                # pytest
├── frontend/                 # Application React (Vite + MUI)
├── deploy/                   # Modèles de configuration (Nginx, systemd)
├── docs/                     # Documentation produit
├── scripts/                  # Scripts d'exploitation (backup, restore, …)
├── docker-compose.yml
└── .env.example
```

## Licence

Tous droits réservés — usage interne pour les institutions du projet GECOR.
Contacter l'administrateur du dépôt pour toute redistribution.
