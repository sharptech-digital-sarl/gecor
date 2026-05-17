#!/usr/bin/env bash
set -euo pipefail

# Crée localement la racine monorepo et y importe
# frontend + backend dans apps/frontend et apps/backend.
#
# Usage:
#   scripts/create-sharptech-monorepo.sh <frontend_repo_url> <backend_repo_url> [branch] [target_dir]

if [[ $# -lt 2 ]]; then
  echo "Usage: $0 <frontend_repo_url> <backend_repo_url> [branch] [target_dir]" >&2
  exit 1
fi

FRONTEND_URL="$1"
BACKEND_URL="$2"
BRANCH="${3:-main}"
TARGET_DIR="${4:-sharptech-digital-sarl}"

if [[ -e "$TARGET_DIR" ]]; then
  echo "Le dossier cible '$TARGET_DIR' existe déjà. Choisissez un autre nom ou supprimez-le." >&2
  exit 1
fi

ssh_to_https() {
  local url="$1"
  if [[ "$url" =~ ^git@github.com:(.+)$ ]]; then
    echo "https://github.com/${BASH_REMATCH[1]}"
    return 0
  fi
  return 1
}

fetch_or_retry_https() {
  local remote_name="$1"
  local branch="$2"

  if git fetch "$remote_name" "$branch"; then
    return 0
  fi

  local current_url
  current_url="$(git remote get-url "$remote_name")"
  local https_url
  if https_url="$(ssh_to_https "$current_url")"; then
    echo "⚠️ Échec via SSH pour '$remote_name'. Nouvelle tentative en HTTPS..." >&2
    git remote set-url "$remote_name" "$https_url"
    git fetch "$remote_name" "$branch"
    return 0
  fi

  return 1
}

cleanup_on_error() {
  local code=$?
  if [[ $code -ne 0 && -d "$TARGET_DIR/.git" ]]; then
    echo "⚠️ Échec de création. Le dossier partiellement créé est conservé: $TARGET_DIR" >&2
    echo "   Vous pouvez le supprimer avec: rm -rf '$TARGET_DIR'" >&2
  fi
  exit "$code"
}
trap cleanup_on_error ERR

mkdir -p "$TARGET_DIR"
cd "$TARGET_DIR"

git init -b "$BRANCH"

git remote add frontend "$FRONTEND_URL"
fetch_or_retry_https frontend "$BRANCH"
git subtree add --prefix=apps/frontend frontend "$BRANCH"

git remote add backend "$BACKEND_URL"
fetch_or_retry_https backend "$BRANCH"
git subtree add --prefix=apps/backend backend "$BRANCH"

cat > README.md <<'README'
# sharptech-digital-sarl monorepo

Ce dépôt monorepo contient :

- `apps/frontend`
- `apps/backend`

Historique importé via `git subtree`.
README

echo "✅ Monorepo créé dans '$TARGET_DIR' avec apps/frontend et apps/backend"
