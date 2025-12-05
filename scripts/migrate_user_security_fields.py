#!/usr/bin/env python3
"""
Migration script to add security fields to User table.
Adds: failed_login_attempts, last_failed_login, locked_until

This script should be run inside the kartoteka_collector Docker container:
  docker exec kartoteka_collector python3 /app/scripts/migrate_user_security_fields.py

Or for development, run it with the correct database path.
"""

import sqlite3
import sys
import os
from pathlib import Path

# Try to find the correct database path
# In Docker container: /app/kartoteka.db
# In development: ../storage/app.db
if os.path.exists("/app/kartoteka.db"):
    db_path = Path("/app/kartoteka.db")
else:
    db_path = Path(__file__).parent.parent / "storage" / "app.db"

if not db_path.exists():
    print(f"Error: Database not found at {db_path}")
    print("Expected locations:")
    print("  - /app/kartoteka.db (Docker)")
    print("  - ./storage/app.db (Development)")
    sys.exit(1)

print(f"Migrating database: {db_path}")

try:
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Check if columns already exist
    cursor.execute("PRAGMA table_info(user)")
    columns = [row[1] for row in cursor.fetchall()]
    
    print(f"Current user table columns: {columns}")
    
    migrations_applied = []
    
    # Add failed_login_attempts column if it doesn't exist
    if "failed_login_attempts" not in columns:
        print("Adding column: failed_login_attempts")
        cursor.execute("ALTER TABLE user ADD COLUMN failed_login_attempts INTEGER DEFAULT 0")
        migrations_applied.append("failed_login_attempts")
    else:
        print("Column failed_login_attempts already exists")
    
    # Add last_failed_login column if it doesn't exist
    if "last_failed_login" not in columns:
        print("Adding column: last_failed_login")
        cursor.execute("ALTER TABLE user ADD COLUMN last_failed_login DATETIME")
        migrations_applied.append("last_failed_login")
    else:
        print("Column last_failed_login already exists")
    
    # Add locked_until column if it doesn't exist
    if "locked_until" not in columns:
        print("Adding column: locked_until")
        cursor.execute("ALTER TABLE user ADD COLUMN locked_until DATETIME")
        migrations_applied.append("locked_until")
    else:
        print("Column locked_until already exists")
    
    # Commit changes
    conn.commit()
    
    if migrations_applied:
        cols_str = ', '.join(migrations_applied)
        print(f"\n✓ Successfully added columns: {cols_str}")
    else:
        print("\n✓ No migration needed - all columns already exist")
    
    # Verify the changes
    cursor.execute("PRAGMA table_info(user)")
    columns_after = [row[1] for row in cursor.fetchall()]
    print(f"\nUser table columns after migration: {columns_after}")
    
    conn.close()
    print("\nMigration completed successfully!")

except sqlite3.Error as e:
    print(f"Error during migration: {e}")
    sys.exit(1)
