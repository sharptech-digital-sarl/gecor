#!/usr/bin/env bash
# =============================================================================
# GECOR — Sauvegarde quotidienne PostgreSQL avec rotation
#
# Lit la connexion depuis $DATABASE_URL (préférence) ou depuis le fichier .env
# situé à la racine du dépôt ou dans backend/.env.
#
# Variables d'environnement reconnues :
#   DATABASE_URL            URL postgres complète (postgresql://user:pwd@host:port/db)
#   BACKUP_DIR              destination des dumps (défaut : /var/backups/gecor)
#   BACKUP_RETENTION_DAYS   conservation rotative (défaut : 30)
#   PG_DUMP_BIN             chemin pg_dump (défaut : `pg_dump`)
#   GZIP_BIN                chemin gzip   (défaut : `gzip`)
#
# Sortie :
#   ${BACKUP_DIR}/gecor_YYYYMMDD-HHMM.dump.gz  (format custom, compressé)
#
# Cron suggéré (utilisateur gecor) :
#   30 2 * * *  gecor  bash /opt/gecor/app/scripts/backup_postgres.sh \
#               >> /var/log/gecor/backup.log 2>&1
# =============================================================================
set -euo pipefail

log() {
    printf '[%s] %s\n' "$(date -u +'%Y-%m-%dT%H:%M:%SZ')" "$*"
}

die() {
    log "ERROR: $*"
    exit 1
}

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

load_env_file() {
    local file="$1"
    [ -f "$file" ] || return 0
    # Charge les KEY=VALUE en ignorant les commentaires
    set +u
    # shellcheck disable=SC1090
    set -a; . "$file"; set +a
    set -u
}

# Si DATABASE_URL n'est pas déjà défini, le charger depuis le .env du dépôt
if [ -z "${DATABASE_URL:-}" ]; then
    load_env_file "${REPO_ROOT}/.env"
fi
if [ -z "${DATABASE_URL:-}" ]; then
    load_env_file "${REPO_ROOT}/backend/.env"
fi

[ -n "${DATABASE_URL:-}" ] || die "DATABASE_URL not set (check .env or environment)"

BACKUP_DIR="${BACKUP_DIR:-/var/backups/gecor}"
BACKUP_RETENTION_DAYS="${BACKUP_RETENTION_DAYS:-30}"
PG_DUMP_BIN="${PG_DUMP_BIN:-pg_dump}"
GZIP_BIN="${GZIP_BIN:-gzip}"

command -v "$PG_DUMP_BIN" >/dev/null 2>&1 || die "pg_dump not found (set PG_DUMP_BIN)"
command -v "$GZIP_BIN"    >/dev/null 2>&1 || die "gzip not found (set GZIP_BIN)"

mkdir -p "$BACKUP_DIR"

TIMESTAMP="$(date -u +'%Y%m%d-%H%M')"
TARGET="${BACKUP_DIR}/gecor_${TIMESTAMP}.dump"

log "Dumping database to ${TARGET}.gz"

# Format custom (-Fc) = portable, restorable avec pg_restore, indépendant de la version
# --no-owner / --no-privileges : restauration plus simple sur un cluster de destination différent
"$PG_DUMP_BIN" \
    --dbname="$DATABASE_URL" \
    --format=custom \
    --no-owner \
    --no-privileges \
    --file="$TARGET"

"$GZIP_BIN" -f "$TARGET"

SIZE="$(du -h "${TARGET}.gz" | awk '{print $1}')"
log "OK — ${TARGET}.gz (${SIZE})"

log "Pruning backups older than ${BACKUP_RETENTION_DAYS} day(s) in ${BACKUP_DIR}"
find "$BACKUP_DIR" -type f -name 'gecor_*.dump.gz' -mtime "+${BACKUP_RETENTION_DAYS}" -print -delete \
    | while read -r f; do log "  pruned $f"; done || true

log "Done."
