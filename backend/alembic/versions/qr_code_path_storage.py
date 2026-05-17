"""visitors.qr_code -> qr_code_path (fichier storage qrcode/), purge anciennes valeurs base64

Revision ID: qr_code_path_storage
Revises: visitor_id_doc
"""
from alembic import op
import sqlalchemy as sa


revision = "qr_code_path_storage"
down_revision = "visitor_id_doc"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(sa.text("ALTER TABLE visitors RENAME COLUMN qr_code TO qr_code_path"))
    # Anciennes lignes : base64 en colonne ; ne sont pas des chemins sous qrcode/
    op.execute(
        sa.text(
            "UPDATE visitors SET qr_code_path = NULL "
            "WHERE qr_code_path IS NOT NULL AND qr_code_path NOT LIKE 'qrcode/%'"
        )
    )


def downgrade() -> None:
    op.execute(sa.text("ALTER TABLE visitors RENAME COLUMN qr_code_path TO qr_code"))
