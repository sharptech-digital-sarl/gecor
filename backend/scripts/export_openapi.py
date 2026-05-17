"""
Exporte le schéma OpenAPI 3 de l'application FastAPI vers un fichier YAML.

Usage (depuis le dossier backend, avec les dépendances installées) :
  python scripts/export_openapi.py
  python scripts/export_openapi.py --out ../schema.yaml

Variables d'environnement factices : évite de nécessiter PostgreSQL pour générer la spec.
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

# Répertoire backend/ sur sys.path (exécution : python scripts/export_openapi.py)
_BACKEND_ROOT = Path(__file__).resolve().parent.parent
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))

# Avant tout import de `app` : config minimale pour create_engine + create_all
# OPENAPI_EXPORT=1 → app.core.config ne surcharge pas ces valeurs avec backend/.env
os.environ["OPENAPI_EXPORT"] = "1"
os.environ.setdefault("SECRET_KEY", "openapi-export-dummy-secret-key-min-32-chars")
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("REDIS_URL", "redis://127.0.0.1:6379/0")
# Valeurs JSON valides pour les champs "complexes" de pydantic-settings
# (évite les erreurs si l'environnement utilisateur contient des chaînes invalides)
os.environ["CORS_ORIGINS"] = '["http://localhost:3000"]'
os.environ["MFA_REQUIRED_ROLES"] = "[]"
os.environ["GOOGLE_CALENDAR_SCOPES"] = '["openid","email","https://www.googleapis.com/auth/calendar.events"]'


def main() -> int:
    parser = argparse.ArgumentParser(description="Export OpenAPI schema to YAML")
    parser.add_argument(
        "--out",
        default=os.path.join(os.path.dirname(__file__), "..", "..", "schema.yaml"),
        help="Chemin du fichier YAML de sortie (défaut: racine du dépôt schema.yaml)",
    )
    args = parser.parse_args()
    out_path = os.path.abspath(args.out)

    try:
        import yaml
    except ImportError:
        print("PyYAML est requis : pip install pyyaml", file=sys.stderr)
        return 1

    from app.main import app

    schema = app.openapi()
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        yaml.dump(
            schema,
            f,
            sort_keys=False,
            allow_unicode=True,
            default_flow_style=False,
        )
    print(f"OpenAPI écrit : {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
