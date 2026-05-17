"""convert_ids_to_uuid

Revision ID: convert_ids_to_uuid
Revises: 
Create Date: 2025-12-15

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from sqlalchemy import inspect
import uuid
import sys
import os

# Add parent directory to path to import models
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from app.core.database import Base
from app.models import *  # Import all models to register them with Base

# revision identifiers, used by Alembic.
revision = 'convert_ids_to_uuid'
down_revision = None  # First migration
branch_labels = None
depends_on = None


def table_exists(table_name: str) -> bool:
    """Check if a table exists in the database."""
    bind = op.get_bind()
    inspector = inspect(bind)
    return table_name in inspector.get_table_names()


def upgrade() -> None:
    # Enable UUID extension if not already enabled
    op.execute('CREATE EXTENSION IF NOT EXISTS "uuid-ossp"')
    
    # Check if users table exists - if not, this is a fresh database
    if not table_exists('users'):
        # Fresh database - create all tables from models with UUID IDs
        bind = op.get_bind()
        Base.metadata.create_all(bind=bind)
        return
    
    # Check if users table has integer ID (needs conversion) or UUID (already converted)
    bind = op.get_bind()
    inspector = inspect(bind)
    users_columns = {col['name']: col['type'] for col in inspector.get_columns('users')}
    
    # If users.id is already UUID, skip conversion
    if 'id' in users_columns:
        id_type = str(users_columns['id'])
        if 'UUID' in id_type or 'uuid' in id_type.lower():
            # Already using UUIDs, skip conversion
            return
    
    # Tables exist with integer IDs - perform conversion
    # Create temporary mapping tables to preserve relationships
    op.execute('''
        CREATE TEMP TABLE id_mapping_users (
            old_id INTEGER PRIMARY KEY,
            new_id UUID NOT NULL
        )
    ''')
    
    op.execute('''
        CREATE TEMP TABLE id_mapping_documents (
            old_id INTEGER PRIMARY KEY,
            new_id UUID NOT NULL
        )
    ''')
    
    op.execute('''
        CREATE TEMP TABLE id_mapping_appointments (
            old_id INTEGER PRIMARY KEY,
            new_id UUID NOT NULL
        )
    ''')
    
    # Generate UUIDs for existing users and store mapping
    op.execute('''
        INSERT INTO id_mapping_users (old_id, new_id)
        SELECT id, gen_random_uuid()
        FROM users
    ''')
    
    # Generate UUIDs for existing documents and store mapping
    op.execute('''
        INSERT INTO id_mapping_documents (old_id, new_id)
        SELECT id, gen_random_uuid()
        FROM mail_documents
    ''')
    
    # Generate UUIDs for existing appointments and store mapping
    op.execute('''
        INSERT INTO id_mapping_appointments (old_id, new_id)
        SELECT id, gen_random_uuid()
        FROM appointments
    ''')
    
    # Convert users table
    op.execute('ALTER TABLE users DROP CONSTRAINT IF EXISTS users_pkey CASCADE')
    op.execute('ALTER TABLE users ADD COLUMN new_id UUID')
    op.execute('''
        UPDATE users u
        SET new_id = m.new_id
        FROM id_mapping_users m
        WHERE u.id = m.old_id
    ''')
    op.execute('ALTER TABLE users DROP COLUMN id')
    op.execute('ALTER TABLE users RENAME COLUMN new_id TO id')
    op.execute('ALTER TABLE users ALTER COLUMN id SET DEFAULT gen_random_uuid()')
    op.execute('ALTER TABLE users ADD PRIMARY KEY (id)')
    
    # Convert mail_documents table
    op.execute('ALTER TABLE mail_documents DROP CONSTRAINT IF EXISTS mail_documents_pkey CASCADE')
    op.execute('ALTER TABLE mail_documents ADD COLUMN new_id UUID')
    op.execute('ALTER TABLE mail_documents ADD COLUMN new_created_by UUID')
    op.execute('ALTER TABLE mail_documents ADD COLUMN new_assigned_to UUID')
    
    op.execute('''
        UPDATE mail_documents d
        SET new_id = m.new_id
        FROM id_mapping_documents m
        WHERE d.id = m.old_id
    ''')
    
    op.execute('''
        UPDATE mail_documents d
        SET new_created_by = m.new_id
        FROM id_mapping_users m
        WHERE d.created_by = m.old_id
    ''')
    
    op.execute('''
        UPDATE mail_documents d
        SET new_assigned_to = m.new_id
        FROM id_mapping_users m
        WHERE d.assigned_to = m.old_id
    ''')
    
    op.execute('ALTER TABLE mail_documents DROP COLUMN id')
    op.execute('ALTER TABLE mail_documents DROP COLUMN created_by')
    op.execute('ALTER TABLE mail_documents DROP COLUMN assigned_to')
    op.execute('ALTER TABLE mail_documents RENAME COLUMN new_id TO id')
    op.execute('ALTER TABLE mail_documents RENAME COLUMN new_created_by TO created_by')
    op.execute('ALTER TABLE mail_documents RENAME COLUMN new_assigned_to TO assigned_to')
    op.execute('ALTER TABLE mail_documents ALTER COLUMN id SET DEFAULT gen_random_uuid()')
    op.execute('ALTER TABLE mail_documents ADD PRIMARY KEY (id)')
    op.execute('ALTER TABLE mail_documents ADD CONSTRAINT mail_documents_created_by_fkey FOREIGN KEY (created_by) REFERENCES users(id)')
    op.execute('ALTER TABLE mail_documents ADD CONSTRAINT mail_documents_assigned_to_fkey FOREIGN KEY (assigned_to) REFERENCES users(id)')
    
    # Convert mail_versions
    op.execute('ALTER TABLE mail_versions DROP CONSTRAINT IF EXISTS mail_versions_pkey CASCADE')
    op.execute('ALTER TABLE mail_versions ADD COLUMN new_id UUID')
    op.execute('ALTER TABLE mail_versions ADD COLUMN new_document_id UUID')
    op.execute('ALTER TABLE mail_versions ADD COLUMN new_created_by UUID')
    
    op.execute('''
        UPDATE mail_versions v
        SET new_id = gen_random_uuid(),
            new_document_id = m.new_id,
            new_created_by = u.new_id
        FROM id_mapping_documents m, id_mapping_users u
        WHERE v.document_id = m.old_id AND v.created_by = u.old_id
    ''')
    
    op.execute('ALTER TABLE mail_versions DROP COLUMN id')
    op.execute('ALTER TABLE mail_versions DROP COLUMN document_id')
    op.execute('ALTER TABLE mail_versions DROP COLUMN created_by')
    op.execute('ALTER TABLE mail_versions RENAME COLUMN new_id TO id')
    op.execute('ALTER TABLE mail_versions RENAME COLUMN new_document_id TO document_id')
    op.execute('ALTER TABLE mail_versions RENAME COLUMN new_created_by TO created_by')
    op.execute('ALTER TABLE mail_versions ALTER COLUMN id SET DEFAULT gen_random_uuid()')
    op.execute('ALTER TABLE mail_versions ADD PRIMARY KEY (id)')
    op.execute('ALTER TABLE mail_versions ADD CONSTRAINT mail_versions_document_id_fkey FOREIGN KEY (document_id) REFERENCES mail_documents(id)')
    op.execute('ALTER TABLE mail_versions ADD CONSTRAINT mail_versions_created_by_fkey FOREIGN KEY (created_by) REFERENCES users(id)')
    
    # Convert workflow_states
    op.execute('ALTER TABLE workflow_states DROP CONSTRAINT IF EXISTS workflow_states_pkey CASCADE')
    op.execute('ALTER TABLE workflow_states ADD COLUMN new_id UUID')
    op.execute('ALTER TABLE workflow_states ADD COLUMN new_document_id UUID')
    
    op.execute('''
        UPDATE workflow_states w
        SET new_id = gen_random_uuid(),
            new_document_id = m.new_id
        FROM id_mapping_documents m
        WHERE w.document_id = m.old_id
    ''')
    
    op.execute('ALTER TABLE workflow_states DROP COLUMN id')
    op.execute('ALTER TABLE workflow_states DROP COLUMN document_id')
    op.execute('ALTER TABLE workflow_states RENAME COLUMN new_id TO id')
    op.execute('ALTER TABLE workflow_states RENAME COLUMN new_document_id TO document_id')
    op.execute('ALTER TABLE workflow_states ALTER COLUMN id SET DEFAULT gen_random_uuid()')
    op.execute('ALTER TABLE workflow_states ADD PRIMARY KEY (id)')
    op.execute('ALTER TABLE workflow_states ADD CONSTRAINT workflow_states_document_id_fkey FOREIGN KEY (document_id) REFERENCES mail_documents(id)')
    
    # Convert workflow_history
    op.execute('ALTER TABLE workflow_history DROP CONSTRAINT IF EXISTS workflow_history_pkey CASCADE')
    op.execute('ALTER TABLE workflow_history ADD COLUMN new_id UUID')
    op.execute('ALTER TABLE workflow_history ADD COLUMN new_document_id UUID')
    op.execute('ALTER TABLE workflow_history ADD COLUMN new_performed_by UUID')
    
    op.execute('''
        UPDATE workflow_history h
        SET new_id = gen_random_uuid(),
            new_document_id = m.new_id,
            new_performed_by = u.new_id
        FROM id_mapping_documents m, id_mapping_users u
        WHERE h.document_id = m.old_id AND h.performed_by = u.old_id
    ''')
    
    op.execute('ALTER TABLE workflow_history DROP COLUMN id')
    op.execute('ALTER TABLE workflow_history DROP COLUMN document_id')
    op.execute('ALTER TABLE workflow_history DROP COLUMN performed_by')
    op.execute('ALTER TABLE workflow_history RENAME COLUMN new_id TO id')
    op.execute('ALTER TABLE workflow_history RENAME COLUMN new_document_id TO document_id')
    op.execute('ALTER TABLE workflow_history RENAME COLUMN new_performed_by TO performed_by')
    op.execute('ALTER TABLE workflow_history ALTER COLUMN id SET DEFAULT gen_random_uuid()')
    op.execute('ALTER TABLE workflow_history ADD PRIMARY KEY (id)')
    op.execute('ALTER TABLE workflow_history ADD CONSTRAINT workflow_history_document_id_fkey FOREIGN KEY (document_id) REFERENCES mail_documents(id)')
    op.execute('ALTER TABLE workflow_history ADD CONSTRAINT workflow_history_performed_by_fkey FOREIGN KEY (performed_by) REFERENCES users(id)')
    
    # Convert appointments
    op.execute('ALTER TABLE appointments DROP CONSTRAINT IF EXISTS appointments_pkey CASCADE')
    op.execute('ALTER TABLE appointments ADD COLUMN new_id UUID')
    op.execute('ALTER TABLE appointments ADD COLUMN new_organizer_id UUID')
    
    op.execute('''
        UPDATE appointments a
        SET new_id = m.new_id,
            new_organizer_id = u.new_id
        FROM id_mapping_appointments m, id_mapping_users u
        WHERE a.id = m.old_id AND a.organizer_id = u.old_id
    ''')
    
    op.execute('ALTER TABLE appointments DROP COLUMN id')
    op.execute('ALTER TABLE appointments DROP COLUMN organizer_id')
    op.execute('ALTER TABLE appointments RENAME COLUMN new_id TO id')
    op.execute('ALTER TABLE appointments RENAME COLUMN new_organizer_id TO organizer_id')
    op.execute('ALTER TABLE appointments ALTER COLUMN id SET DEFAULT gen_random_uuid()')
    op.execute('ALTER TABLE appointments ADD PRIMARY KEY (id)')
    op.execute('ALTER TABLE appointments ADD CONSTRAINT appointments_organizer_id_fkey FOREIGN KEY (organizer_id) REFERENCES users(id)')
    
    # Convert visitors
    op.execute('ALTER TABLE visitors DROP CONSTRAINT IF EXISTS visitors_pkey CASCADE')
    op.execute('ALTER TABLE visitors ADD COLUMN new_id UUID')
    op.execute('ALTER TABLE visitors ADD COLUMN new_appointment_id UUID')
    
    op.execute('''
        UPDATE visitors v
        SET new_id = gen_random_uuid(),
            new_appointment_id = m.new_id
        FROM id_mapping_appointments m
        WHERE v.appointment_id = m.old_id
    ''')
    
    op.execute('ALTER TABLE visitors DROP COLUMN id')
    op.execute('ALTER TABLE visitors DROP COLUMN appointment_id')
    op.execute('ALTER TABLE visitors RENAME COLUMN new_id TO id')
    op.execute('ALTER TABLE visitors RENAME COLUMN new_appointment_id TO appointment_id')
    op.execute('ALTER TABLE visitors ALTER COLUMN id SET DEFAULT gen_random_uuid()')
    op.execute('ALTER TABLE visitors ADD PRIMARY KEY (id)')
    op.execute('ALTER TABLE visitors ADD CONSTRAINT visitors_appointment_id_fkey FOREIGN KEY (appointment_id) REFERENCES appointments(id)')
    
    # Convert signatures
    op.execute('ALTER TABLE signatures DROP CONSTRAINT IF EXISTS signatures_pkey CASCADE')
    op.execute('ALTER TABLE signatures ADD COLUMN new_id UUID')
    op.execute('ALTER TABLE signatures ADD COLUMN new_document_id UUID')
    op.execute('ALTER TABLE signatures ADD COLUMN new_user_id UUID')
    
    op.execute('''
        UPDATE signatures s
        SET new_id = gen_random_uuid(),
            new_document_id = m.new_id,
            new_user_id = u.new_id
        FROM id_mapping_documents m, id_mapping_users u
        WHERE s.document_id = m.old_id AND s.user_id = u.old_id
    ''')
    
    op.execute('ALTER TABLE signatures DROP COLUMN id')
    op.execute('ALTER TABLE signatures DROP COLUMN document_id')
    op.execute('ALTER TABLE signatures DROP COLUMN user_id')
    op.execute('ALTER TABLE signatures RENAME COLUMN new_id TO id')
    op.execute('ALTER TABLE signatures RENAME COLUMN new_document_id TO document_id')
    op.execute('ALTER TABLE signatures RENAME COLUMN new_user_id TO user_id')
    op.execute('ALTER TABLE signatures ALTER COLUMN id SET DEFAULT gen_random_uuid()')
    op.execute('ALTER TABLE signatures ADD PRIMARY KEY (id)')
    op.execute('ALTER TABLE signatures ADD CONSTRAINT signatures_document_id_fkey FOREIGN KEY (document_id) REFERENCES mail_documents(id)')
    op.execute('ALTER TABLE signatures ADD CONSTRAINT signatures_user_id_fkey FOREIGN KEY (user_id) REFERENCES users(id)')
    
    # Convert notifications
    op.execute('ALTER TABLE notifications DROP CONSTRAINT IF EXISTS notifications_pkey CASCADE')
    op.execute('ALTER TABLE notifications ADD COLUMN new_id UUID')
    op.execute('ALTER TABLE notifications ADD COLUMN new_recipient_id UUID')
    op.execute('ALTER TABLE notifications ADD COLUMN new_related_document_id UUID')
    op.execute('ALTER TABLE notifications ADD COLUMN new_related_appointment_id UUID')
    
    # Update notifications - handle NULL recipient_id separately
    op.execute('''
        UPDATE notifications
        SET new_id = gen_random_uuid(),
            new_recipient_id = CASE 
                WHEN recipient_id IS NOT NULL THEN (
                    SELECT new_id FROM id_mapping_users WHERE old_id = notifications.recipient_id
                )
                ELSE NULL 
            END,
            new_related_document_id = CASE 
                WHEN related_document_id IS NOT NULL THEN (
                    SELECT new_id FROM id_mapping_documents WHERE old_id = notifications.related_document_id
                )
                ELSE NULL 
            END,
            new_related_appointment_id = CASE 
                WHEN related_appointment_id IS NOT NULL THEN (
                    SELECT new_id FROM id_mapping_appointments WHERE old_id = notifications.related_appointment_id
                )
                ELSE NULL 
            END
    ''')
    
    op.execute('ALTER TABLE notifications DROP COLUMN id')
    op.execute('ALTER TABLE notifications DROP COLUMN recipient_id')
    op.execute('ALTER TABLE notifications DROP COLUMN related_document_id')
    op.execute('ALTER TABLE notifications DROP COLUMN related_appointment_id')
    op.execute('ALTER TABLE notifications RENAME COLUMN new_id TO id')
    op.execute('ALTER TABLE notifications RENAME COLUMN new_recipient_id TO recipient_id')
    op.execute('ALTER TABLE notifications RENAME COLUMN new_related_document_id TO related_document_id')
    op.execute('ALTER TABLE notifications RENAME COLUMN new_related_appointment_id TO related_appointment_id')
    op.execute('ALTER TABLE notifications ALTER COLUMN id SET DEFAULT gen_random_uuid()')
    op.execute('ALTER TABLE notifications ADD PRIMARY KEY (id)')
    op.execute('ALTER TABLE notifications ADD CONSTRAINT notifications_recipient_id_fkey FOREIGN KEY (recipient_id) REFERENCES users(id)')
    op.execute('ALTER TABLE notifications ADD CONSTRAINT notifications_related_document_id_fkey FOREIGN KEY (related_document_id) REFERENCES mail_documents(id)')
    op.execute('ALTER TABLE notifications ADD CONSTRAINT notifications_related_appointment_id_fkey FOREIGN KEY (related_appointment_id) REFERENCES appointments(id)')
    
    # Drop temporary tables (they're TEMP so they'll be dropped automatically, but explicit is better)
    # TEMP tables are automatically dropped at end of session


def downgrade() -> None:
    # Note: Downgrading from UUID to Integer is complex and may lose data
    # This is a placeholder - implement if needed
    pass
