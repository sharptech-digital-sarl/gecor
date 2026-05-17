#!/usr/bin/env python3
"""Test d’envoi SMTP avec la même config que l’API.

Fichiers .env (dev local) : `backend/.env` puis `backend/app/.env` (voir app.core.config).

Sous Docker Compose, le backend charge aussi (si présents) `.env` à la racine,
`backend/.env` et `backend/app/.env` via `env_file` — définissez-y `SMTP_*`, puis
recréez le conteneur : `docker compose up -d backend`.

Usage (depuis le dossier backend) :
  python scripts/test_smtp.py --to destinataire@example.com

Sous Docker (depuis la racine du projet, après `docker compose up -d`) :
  docker compose exec backend python scripts/test_smtp.py --to destinataire@example.com

Le dossier `backend/scripts` est monté dans le conteneur (voir docker-compose.yml).
Sinon, reconstruire l’image : `docker compose build backend && docker compose up -d backend`.
"""
from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

# Racine du backend (répertoire parent de scripts/)
_BACKEND_ROOT = Path(__file__).resolve().parent.parent
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))


async def main() -> int:
    parser = argparse.ArgumentParser(description="Tester l’envoi d’e-mail via SMTP (config FPI-CONNECT).")
    parser.add_argument(
        "--to",
        required=True,
        help="Adresse e-mail du destinataire",
    )
    parser.add_argument(
        "--subject",
        default="[FPI-CONNECT] Test SMTP",
        help="Sujet du message",
    )
    args = parser.parse_args()

    # Charge settings (backend/.env + backend/app/.env sauf si OPENAPI_EXPORT=1)
    from app.core.config import settings
    from app.services.notification_service import notification_service

    print("Configuration SMTP lue par l’application :")
    print(f"  SMTP_HOST     = {settings.SMTP_HOST!r}")
    print(f"  SMTP_PORT     = {settings.SMTP_PORT}")
    print(f"  SMTP_USER     = {settings.SMTP_USER!r}")
    print(f"  SMTP_PASSWORD = {'***' if settings.SMTP_PASSWORD else None}")
    print(f"  SMTP_FROM     = {settings.SMTP_FROM!r}")
    print(f"  SMTP_USE_TLS  = {settings.SMTP_USE_TLS}")
    print()

    if not settings.SMTP_HOST:
        print("Erreur : SMTP_HOST est vide. Définissez SMTP_* dans backend/.env, backend/app/.env ou l’environnement.")
        print("Sous Docker : après modification des .env, exécutez `docker compose up -d backend` pour recharger env_file.")
        return 1

    plain = (
        "Ceci est un e-mail de test envoyé depuis la console (scripts/test_smtp.py).\n"
        "Si vous recevez ce message, la configuration SMTP est correcte.\n"
    )
    html = (
        "<p>Ceci est un <strong>e-mail de test</strong> envoyé depuis "
        "<code>scripts/test_smtp.py</code>.</p>"
        "<p>Si vous recevez ce message, la configuration SMTP est correcte.</p>"
    )

    print(f"Envoi vers {args.to!r} …")
    ok = await notification_service.send_email(
        to_email=args.to.strip(),
        subject=args.subject,
        message=plain,
        html_message=html,
    )
    if ok:
        print("Succès : l’e-mail a été accepté par le serveur SMTP (vérifiez la boîte / spams).")
        return 0
    print("Échec : consultez les logs du serveur (erreur SMTP ou refus).")
    return 2


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
