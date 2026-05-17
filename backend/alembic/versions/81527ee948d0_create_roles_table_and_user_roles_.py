"""create_roles_table_and_user_roles_junction

Revision ID: 81527ee948d0
Revises: add_mfa_and_refresh_sessions
Create Date: 2025-12-25 12:13:20.187862

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from sqlalchemy import inspect
import uuid


# revision identifiers, used by Alembic.
revision = '81527ee948d0'
down_revision = 'add_mfa_and_refresh_sessions'
branch_labels = None
depends_on = None


def table_exists(table_name: str) -> bool:
    """Check if a table exists in the database."""
    bind = op.get_bind()
    inspector = inspect(bind)
    return table_name in inspector.get_table_names()


def column_exists(table_name: str, column_name: str) -> bool:
    """Check if a column exists in a table."""
    bind = op.get_bind()
    inspector = inspect(bind)
    if not table_exists(table_name):
        return False
    columns = [col['name'] for col in inspector.get_columns(table_name)]
    return column_name in columns


def upgrade() -> None:
    # Create roles table
    if not table_exists('roles'):
        op.create_table(
            'roles',
            sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
            sa.Column('name', sa.String(), nullable=False),
            sa.Column('description', sa.String(), nullable=True),
            sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        )
        op.create_index(op.f('ix_roles_id'), 'roles', ['id'], unique=False)
        op.create_index(op.f('ix_roles_name'), 'roles', ['name'], unique=True)
    
    # Create user_roles junction table
    if not table_exists('user_roles'):
        op.create_table(
            'user_roles',
            sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
            sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column('role_id', postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
            sa.ForeignKeyConstraint(['role_id'], ['roles.id'], ondelete='CASCADE'),
            sa.UniqueConstraint('user_id', 'role_id', name='uq_user_role'),
            comment='Junction table linking users to roles'
        )
        op.create_index(op.f('ix_user_roles_id'), 'user_roles', ['id'], unique=False)
        op.create_index(op.f('ix_user_roles_user_id'), 'user_roles', ['user_id'], unique=False)
        op.create_index(op.f('ix_user_roles_role_id'), 'user_roles', ['role_id'], unique=False)
    
    # Migrate existing role data from users.role column to roles and user_roles tables
    if column_exists('users', 'role'):
        # Insert roles if they don't exist
        role_mapping = {
            'master': 'Master Administrator',
            'director': 'Director',
            'secretary': 'Secretary',
            'analyst': 'Analyst',
            'receptionist': 'Receptionist',
            'guest': 'Guest'
        }
        
        # Create a temporary table to store role name to role_id mapping
        op.execute('''
            CREATE TEMP TABLE role_name_to_id (
                role_name VARCHAR PRIMARY KEY,
                role_id UUID
            )
        ''')
        
        # Insert roles if they don't exist
        for role_name, description in role_mapping.items():
            op.execute(f'''
                INSERT INTO roles (id, name, description, created_at, updated_at)
                SELECT gen_random_uuid(), '{role_name}', '{description}', NOW(), NOW()
                WHERE NOT EXISTS (SELECT 1 FROM roles WHERE name = '{role_name}')
            ''')
        
        # Get role IDs and store in temp table
        for role_name in role_mapping.keys():
            op.execute(f'''
                INSERT INTO role_name_to_id (role_name, role_id)
                SELECT '{role_name}', id FROM roles WHERE name = '{role_name}'
            ''')
        
        # Migrate user roles from users.role to user_roles table
        # Map old 'admin' role to 'master' role
        op.execute('''
            INSERT INTO user_roles (id, user_id, role_id, created_at)
            SELECT 
                gen_random_uuid(),
                u.id,
                CASE 
                    WHEN LOWER(u.role::text) = 'admin' THEN (SELECT role_id FROM role_name_to_id WHERE role_name = 'master')
                    ELSE r.role_id
                END,
                NOW()
            FROM users u
            CROSS JOIN role_name_to_id r
            WHERE (LOWER(u.role::text) = r.role_name OR LOWER(u.role::text) = 'admin')
            AND NOT EXISTS (
                SELECT 1 FROM user_roles ur 
                WHERE ur.user_id = u.id AND ur.role_id = CASE 
                    WHEN LOWER(u.role::text) = 'admin' THEN (SELECT role_id FROM role_name_to_id WHERE role_name = 'master')
                    ELSE r.role_id
                END
            )
        ''')
        
        # Drop the role column from users table
        op.drop_column('users', 'role')
    
    # If role column doesn't exist but roles table is empty, seed it with default roles
    elif table_exists('roles'):
        bind = op.get_bind()
        result = bind.execute(sa.text("SELECT COUNT(*) FROM roles"))
        count = result.scalar()
        if count == 0:
            role_mapping = {
                'admin': 'Administrator',
                'director': 'Director',
                'secretary': 'Secretary',
                'analyst': 'Analyst',
                'receptionist': 'Receptionist',
                'guest': 'Guest'
            }
            for role_name, description in role_mapping.items():
                op.execute(f'''
                    INSERT INTO roles (id, name, description, created_at, updated_at)
                    VALUES (gen_random_uuid(), '{role_name}', '{description}', NOW(), NOW())
                ''')


def downgrade() -> None:
    # Add role column back to users table
    if not column_exists('users', 'role'):
        op.add_column('users', sa.Column('role', postgresql.ENUM('master', 'director', 'secretary', 'analyst', 'receptionist', 'guest', name='userrole'), nullable=True))
        
        # Migrate data back from user_roles to users.role
        # Get the first role for each user (or default to 'guest')
        op.execute('''
            UPDATE users u
            SET role = COALESCE(
                (SELECT r.name::userrole 
                 FROM user_roles ur 
                 JOIN roles r ON ur.role_id = r.id 
                 WHERE ur.user_id = u.id 
                 LIMIT 1),
                'guest'::userrole
            )
        ''')
        
        # Make role column NOT NULL after migration
        op.alter_column('users', 'role', nullable=False, server_default="'guest'::userrole")
    
    # Drop junction table
    if table_exists('user_roles'):
        op.drop_index(op.f('ix_user_roles_role_id'), table_name='user_roles')
        op.drop_index(op.f('ix_user_roles_user_id'), table_name='user_roles')
        op.drop_index(op.f('ix_user_roles_id'), table_name='user_roles')
        op.drop_table('user_roles')
    
    # Drop roles table
    if table_exists('roles'):
        op.drop_index(op.f('ix_roles_name'), table_name='roles')
        op.drop_index(op.f('ix_roles_id'), table_name='roles')
        op.drop_table('roles')

