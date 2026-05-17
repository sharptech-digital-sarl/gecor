#!/usr/bin/env bash
# =============================================================================
# GECOR — Restauration d'un dump PostgreSQL généré par backup_postgres.sh
#
# Usage : bash scripts/restore_postgres.sh <fichier.dump.gz> [database_url]
#
# Comportement :
#   - Décompresse le dump dans un fichier temporaire (s'il est .gz)
#   - Drop/Crée la base cible (option --clean --create de pg_restore)
#   - Ne touche pas les rôles existants (option --no-owner)
#
# Sécurité : ne JAMAIS lancer ce script sur la base de production sans avoir
# confirmé la procédure de bascule. Préférer le faire sur une instance de
# récupération distincte.
# =============================================================================
set -euo pipefail

log() { printf '[%s] %s\n' "$(date -u +'%Y-%m-%dT%H:%M:%SZ')" "$*"; }
die() { log "ERROR: $*"; exit 1; }

[ $# -ge 1 ] || die "Usage: $0 <fichier.dump.gz> [database_url]"
DUMP_FILE="$1"
DB_URL="${2:-${DATABASE_URL:-}}"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

load_env_file() {
    local file="$1"
    [ -f "$file" ] || return 0
    set +u; set -a; . "$file"; set +a; set -u
}
if [ -z "$DB_URL" ]; then load_env_file "${REPO_ROOT}/.env"; DB_URL="${DATABASE_URL:-}"; fi
if [ -z "$DB_URL" ]; then load_env_file "${REPO_ROOT}/backend/.env"; DB_URL="${DATABASE_URL:-}"; fi
[ -n "$DB_URL" ] || die "DATABASE_URL not provided (argument or .env)"
[ -f "$DUMP_FILE" ] || die "Dump file not found: $DUMP_FILE"

PG_RESTORE_BIN="${PG_RESTORE_BIN:-pg_restore}"
command -v "$PG_RESTORE_BIN" >/dev/null 2>&1 || die "pg_restore not found"

TMP=""
cleanup() { [ -n "$TMP" ] && [ -f "$TMP" ] && rm -f "$TMP"; }
trap cleanup EXIT

INPUT="$DUMP_FILE"
case "$DUMP_FILE" in
    *.gz)
        TMP="$(mktemp --suffix=.dump)"
        log "Decompressing $DUMP_FILE -> $TMP"
        gunzip -c "$DUMP_FILE" > "$TMP"
        INPUT="$TMP"
        ;;
esac

read -r -p "About to restore '$INPUT' into '$DB_URL'. Continue? [y/N] " CONFIRM
case "$CONFIRM" in
    y|Y|yes|YES) ;;
    *) die "Aborted by user." ;;
esac

log "Restoring with pg_restore (this will DROP existing objects)…"
"$PG_RESTORE_BIN" \
    --dbname="$DB_URL" \
    --clean --if-exists \
    --no-owner --no-privileges \
    --exit-on-error \
    "$INPUT"

log "Restore complete. Re-run Alembic check: 'cd backend && alembic current'"
