#!/usr/bin/env python3
"""
Migration script to add security fields to User table.

Adds:
- is_admin (boolean, default False)
- failed_login_attempts (integer, default 0)
- last_failed_login (datetime, nullable)
- locked_until (datetime, nullable)

Usage:
    python migrate_add_security_fields.py
"""

import os
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))

from sqlalchemy import text, inspect
from kartoteka_web.database import engine


def column_exists(table_name: str, column_name: str) -> bool:
    """Check if a column exists in a table."""
    inspector = inspect(engine)
    columns = [col['name'] for col in inspector.get_columns(table_name)]
    return column_name in columns


def migrate():
    """Run migration to add security fields to User table."""
    print("🔄 Starting migration: Adding security fields to User table...")
    
    with engine.connect() as conn:
        # Check which columns need to be added
        columns_to_add = []
        
        if not column_exists('user', 'is_admin'):
            columns_to_add.append(('is_admin', 'BOOLEAN DEFAULT 0'))
            
        if not column_exists('user', 'failed_login_attempts'):
            columns_to_add.append(('failed_login_attempts', 'INTEGER DEFAULT 0'))
            
        if not column_exists('user', 'last_failed_login'):
            columns_to_add.append(('last_failed_login', 'TIMESTAMP NULL'))
            
        if not column_exists('user', 'locked_until'):
            columns_to_add.append(('locked_until', 'TIMESTAMP NULL'))
        
        if not columns_to_add:
            print("✅ All security fields already exist. Nothing to migrate.")
            return
        
        # Add missing columns
        for column_name, column_def in columns_to_add:
            try:
                sql = f"ALTER TABLE user ADD COLUMN {column_name} {column_def}"
                print(f"   Adding column: {column_name}")
                conn.execute(text(sql))
                conn.commit()
                print(f"   ✅ Added: {column_name}")
            except Exception as e:
                print(f"   ⚠️  Error adding {column_name}: {e}")
                # Continue with other columns even if one fails
        
        print("\n✅ Migration completed successfully!")
        print(f"   Added {len(columns_to_add)} column(s) to User table")
        
        # Verify the changes
        print("\n🔍 Verifying changes...")
        result = conn.execute(text("PRAGMA table_info(user)"))
        columns = result.fetchall()
        
        print("   Current User table columns:")
        for col in columns:
            print(f"     - {col[1]} ({col[2]})")


if __name__ == "__main__":
    try:
        migrate()
    except Exception as e:
        print(f"\n❌ Migration failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
