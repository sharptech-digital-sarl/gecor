# =============================================================================
# Makefile GECOR — raccourcis pour les tâches courantes
# Utilisation : `make help`
# =============================================================================

.DEFAULT_GOAL := help

# Couleurs
GREEN  := \033[32m
YELLOW := \033[33m
RESET  := \033[0m

# Chemins
BACKEND  := backend
FRONTEND := frontend

.PHONY: help install install-backend install-frontend dev dev-backend dev-frontend
.PHONY: lint lint-backend lint-frontend format format-backend test test-backend
.PHONY: openapi backup restore docker-up docker-down docker-logs clean

help: ## Affiche cette aide
	@printf "$(GREEN)Cibles disponibles :$(RESET)\n"
	@awk 'BEGIN {FS = ":.*##"} /^[a-zA-Z_-]+:.*##/ \
	  { printf "  $(YELLOW)%-22s$(RESET) %s\n", $$1, $$2 }' $(MAKEFILE_LIST)

# ---------------------------------------------------------------------------- Installation
install: install-backend install-frontend ## Installe dépendances back + front

install-backend: ## Installe les dépendances Python (+ dev)
	cd $(BACKEND) && pip install -r requirements.txt -r requirements-dev.txt

install-frontend: ## Installe les dépendances npm
	cd $(FRONTEND) && npm install

# ---------------------------------------------------------------------------- Développement
dev-backend: ## Lance l'API en mode dev (Uvicorn --reload)
	cd $(BACKEND) && uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

dev-frontend: ## Lance le frontend Vite
	cd $(FRONTEND) && npm run dev

# ---------------------------------------------------------------------------- Qualité
lint: lint-backend lint-frontend ## Lint complet (ruff + eslint)

lint-backend: ## Lint Python (ruff + black --check)
	cd $(BACKEND) && ruff check . && black --check .

lint-frontend: ## Lint TypeScript (eslint)
	cd $(FRONTEND) && npm run lint

format: format-backend ## Format Python (black + ruff --fix)

format-backend:
	cd $(BACKEND) && ruff check --fix . && black .

# ---------------------------------------------------------------------------- Tests
test: test-backend ## Lance les tests backend (pytest)

test-backend:
	cd $(BACKEND) && pytest

# ---------------------------------------------------------------------------- OpenAPI
openapi: ## Exporte le schéma OpenAPI YAML à la racine du dépôt
	cd $(BACKEND) && python scripts/export_openapi.py --out ../schema.yaml

# ---------------------------------------------------------------------------- Sauvegarde
backup: ## Sauvegarde PostgreSQL (pg_dump compressé + rotation 30j)
	bash scripts/backup_postgres.sh

restore: ## Restaure un dump PostgreSQL. Usage : make restore FILE=/path/to/dump.gz
	@test -n "$(FILE)" || (printf "Usage: make restore FILE=/path/to/dump.gz\n" && exit 1)
	bash scripts/restore_postgres.sh "$(FILE)"

# ---------------------------------------------------------------------------- Docker
docker-up: ## Démarre la stack Docker (build + up -d)
	docker compose up -d --build

docker-down: ## Arrête la stack Docker
	docker compose down

docker-logs: ## Tail des logs Docker (backend + celery)
	docker compose logs -f --tail=200 backend celery-worker celery-beat

# ---------------------------------------------------------------------------- Divers
clean: ## Supprime caches Python / dist frontend
	find . -type d -name __pycache__ -prune -exec rm -rf {} +
	find . -type d -name ".pytest_cache" -prune -exec rm -rf {} +
	rm -rf $(FRONTEND)/dist $(FRONTEND)/.vite
