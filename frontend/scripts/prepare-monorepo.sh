#!/usr/bin/env bash
set -euo pipefail

# Prépare un dépôt monorepo "gecor" en important frontend + backend avec git subtree.
# Usage:
#   scripts/prepare-monorepo.sh <frontend_repo_url> <backend_repo_url> [default_branch]

if [[ $# -lt 2 ]]; then
  echo "Usage: $0 <frontend_repo_url> <backend_repo_url> [default_branch]"
  exit 1
fi

FRONTEND_URL="$1"
BACKEND_URL="$2"
BRANCH="${3:-main}"

if [[ -d .git ]]; then
  echo "Le dossier courant contient déjà un dépôt Git. Exécutez ce script dans un dossier vide destiné au monorepo." >&2
  exit 1
fi

git init

git checkout -b "$BRANCH"

git remote add frontend "$FRONTEND_URL"
git fetch frontend

git subtree add --prefix=apps/frontend frontend "$BRANCH"

git remote add backend "$BACKEND_URL"
git fetch backend

git subtree add --prefix=apps/backend backend "$BRANCH"

echo "✅ Monorepo initialisé avec apps/frontend et apps/backend"
