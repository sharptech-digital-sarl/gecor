#!/usr/bin/env python
"""Script to create initial master user"""
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy.orm import Session
from app.core.config import DEFAULT_INITIAL_ADMIN_PASSWORD
from app.core.database import SessionLocal
from app.core.security import get_password_hash
from app.models.user import User
from app.models.role import Role

def create_admin(
    username: str = "admin",
    email: str = "admin@gecor.local",
    password: str = DEFAULT_INITIAL_ADMIN_PASSWORD,
    full_name: str = "System Administrator",
):
    """Create master user (function name kept for backward compatibility)"""
    db: Session = SessionLocal()
    try:
        # Check if user already exists
        existing = db.query(User).filter(User.username == username).first()
        if existing:
            print(f"User {username} already exists!")
            return
        
        # Get or create master role
        master_role = db.query(Role).filter(Role.name == "master").first()
        if not master_role:
            master_role = Role(name="master", description="Master Administrator")
            db.add(master_role)
            db.flush()  # Flush to get the role ID
        
        # Create master user
        master_user = User(
            username=username,
            email=email,
            hashed_password=get_password_hash(password),
            full_name=full_name,
            is_active=True,
            is_superuser=True
        )
        
        # Assign master role
        master_user.roles = [master_role]
        
        db.add(master_user)
        db.commit()
        print(f"Master user created successfully!")
        print(f"Username: {username}")
        print(f"Email: {email}")
        print(f"Password: {password}")
        print("Please change the password after first login!")
    
    except Exception as e:
        db.rollback()
        print(f"Error creating master user: {str(e)}")
    finally:
        db.close()


def reset_admin_password(username: str, password: str) -> int:
    """Set a new password for an existing user (by username)."""
    db: Session = SessionLocal()
    try:
        user = db.query(User).filter(User.username == username).first()
        if not user:
            print(f"User « {username} » not found.")
            print(
                "Create the account first (run this script without --reset), "
                "or use --ensure to create or reset in one step."
            )
            return 1
        user.hashed_password = get_password_hash(password)
        db.commit()
        print(f"Password updated for « {username} ».")
        print("Log in with the new password (change it after first login if needed).")
        return 0
    except Exception as e:
        db.rollback()
        print(f"Error updating password: {str(e)}")
        return 1
    finally:
        db.close()


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Create or reset master user password")
    parser.add_argument("--username", default="admin", help="Master username")
    parser.add_argument("--email", default="admin@gecor.local", help="Master email")
    parser.add_argument(
        "--password",
        default=DEFAULT_INITIAL_ADMIN_PASSWORD,
        help="Master password (new password when using --reset); default matches PASSWORD_RESET_POLICY_DEFAULT",
    )
    parser.add_argument("--full-name", default="System Administrator", help="Master full name")
    parser.add_argument(
        "--reset",
        action="store_true",
        help="Reset password for an existing user (username must exist)",
    )
    parser.add_argument(
        "--ensure",
        action="store_true",
        help="Create master user if missing, otherwise reset password (handy after a new Docker DB)",
    )

    args = parser.parse_args()
    if args.reset and args.ensure:
        parser.error("Use only one of --reset or --ensure")
    if args.ensure:
        if reset_admin_password(args.username, args.password) == 0:
            raise SystemExit(0)
        create_admin(args.username, args.email, args.password, args.full_name)
        raise SystemExit(0)
    if args.reset:
        raise SystemExit(reset_admin_password(args.username, args.password))
    create_admin(args.username, args.email, args.password, args.full_name)

