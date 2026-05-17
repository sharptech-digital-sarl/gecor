# Installation et déploiement GECOR

Trois modes sont supportés :

1. **Docker Compose** — recommandé pour le développement et la pré-production.
2. **Installation native** — pour le développement local rapide ou les
   environnements où Docker n'est pas disponible.
3. **Production on-premise** — PostgreSQL/Redis dédiés, Gunicorn + Nginx,
   stockage local ou NAS, sauvegarde quotidienne.

## 1. Docker Compose (dev / pré-prod)

### Prérequis

- Docker ≥ 24
- Docker Compose plugin ≥ 2.20

### Étapes

```bash
git clone <repo> gecor && cd gecor
cp .env.example .env
# Editer .env :
# - SECRET_KEY (chaîne aléatoire de 32+ caractères)
# - POSTGRES_PASSWORD / DATABASE_URL alignés
# - VITE_API_URL si vous changez les ports
docker compose up -d --build
docker compose exec backend python -m app.scripts.create_admin \
    --username admin --email admin@gecor.local
```

Ports exposés (par défaut) :

- **Frontend** : <http://localhost:3001>
- **Backend** : <http://localhost:8001> (Swagger sur `/docs`)
- **PostgreSQL** : `localhost:5435`
- **Redis** : `localhost:6380`

### Mise à jour

```bash
git pull
docker compose build --pull
docker compose up -d
# Les migrations Alembic sont appliquées automatiquement (commande backend).
```

## 2. Installation native (développement)

### Prérequis

- Python 3.12+
- Node.js 18+ (LTS recommandé)
- PostgreSQL 15+
- Redis 7+
- Tesseract 5 + langues `fra` et `eng` + Poppler

```bash
# Debian / Ubuntu
sudo apt install -y python3.12 python3.12-venv \
    postgresql-15 postgresql-contrib redis-server \
    tesseract-ocr tesseract-ocr-fra tesseract-ocr-eng poppler-utils \
    nodejs npm
```

### Backend

```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
pip install -r requirements-dev.txt   # tests + linters (optionnel)
cp .env.example .env                  # ajuster DATABASE_URL, SECRET_KEY, …
python wait_for_db.py
alembic upgrade head
python -m app.scripts.create_admin
uvicorn app.main:app --reload --port 8000
```

### Frontend

```bash
cd frontend
npm install
cp .env.example .env   # VITE_API_URL=http://localhost:8000/api/v1
npm run dev
```

### Celery (optionnel mais nécessaire pour OCR / rappels)

```bash
cd backend && source .venv/bin/activate
celery -A app.celery_app worker --loglevel=info
celery -A app.celery_app beat --loglevel=info
```

## 3. Production on-premise (Gunicorn + Nginx + systemd)

### 3.1 Préparer l'OS

Utilisateur de service dédié, exemple :

```bash
sudo adduser --system --group --home /opt/gecor gecor
sudo mkdir -p /opt/gecor/storage /var/log/gecor
sudo chown -R gecor:gecor /opt/gecor /var/log/gecor
```

### 3.2 Déployer le code

```bash
sudo -u gecor git clone <repo> /opt/gecor/app
cd /opt/gecor/app/backend
sudo -u gecor python3.12 -m venv .venv
sudo -u gecor .venv/bin/pip install -r requirements.txt gunicorn
sudo -u gecor cp .env.example .env  # ajuster
sudo -u gecor .venv/bin/alembic upgrade head
sudo -u gecor .venv/bin/python -m app.scripts.create_admin
```

Frontend build :

```bash
cd /opt/gecor/app/frontend
sudo -u gecor npm ci
sudo -u gecor VITE_API_URL=/api/v1 npm run build
# Les fichiers statiques se trouvent dans /opt/gecor/app/frontend/dist
```

### 3.3 Service systemd (Gunicorn)

Modèle : [`deploy/gecor-gunicorn.service.example`](../deploy/gecor-gunicorn.service.example).

```bash
sudo cp deploy/gecor-gunicorn.service.example /etc/systemd/system/gecor-api.service
# Ajuster les chemins et la variable EnvironmentFile au besoin
sudo systemctl daemon-reload
sudo systemctl enable --now gecor-api.service
```

Service Celery worker (optionnel) :

```bash
sudo cp deploy/gecor-celery-worker.service.example /etc/systemd/system/gecor-celery-worker.service
sudo cp deploy/gecor-celery-beat.service.example /etc/systemd/system/gecor-celery-beat.service
sudo systemctl enable --now gecor-celery-worker gecor-celery-beat
```

### 3.4 Nginx (reverse-proxy + serveur du SPA)

Modèle : [`deploy/nginx.conf.example`](../deploy/nginx.conf.example).

```bash
sudo cp deploy/nginx.conf.example /etc/nginx/sites-available/gecor.conf
sudo ln -s /etc/nginx/sites-available/gecor.conf /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx
```

Pensez à terminer TLS au niveau Nginx (Let's Encrypt en LAN n'est pas possible ;
utiliser une PKI interne ou un certificat self-signed accepté par la flotte).

### 3.5 Sauvegarde

Voir [`maintenance.md`](maintenance.md) et `scripts/backup_postgres.sh`.

Cron suggéré (utilisateur `gecor`) :

```cron
# /etc/cron.d/gecor-backup
30 2 * * *  gecor  bash /opt/gecor/app/scripts/backup_postgres.sh >> /var/log/gecor/backup.log 2>&1
```
