"""
Personal Money Flow Tracker - Database Initialization & Verification Script
Usage:
    python init_db.py
    python init_db.py "postgresql://user:password@host/dbname?sslmode=require"
"""

import sys
import os

# If database URL is passed as a CLI argument, set it in environment
if len(sys.argv) > 1:
    os.environ["DATABASE_URL"] = sys.argv[1]

from app import create_app
from app.extensions import db
from flask_migrate import upgrade
import sqlalchemy

app = create_app("production")

with app.app_context():
    db_uri = app.config.get("SQLALCHEMY_DATABASE_URI")
    # Mask password for secure logging
    masked_uri = db_uri
    if "@" in db_uri and ":" in db_uri:
        try:
            prefix, rest = db_uri.split("://", 1)
            creds, host_part = rest.split("@", 1)
            user = creds.split(":")[0]
            masked_uri = f"{prefix}://{user}:*****@{host_part}"
        except Exception:
            pass

    print(f"[*] Target Database URI: {masked_uri}")
    print("[*] Testing database connectivity...")

    try:
        with db.engine.connect() as conn:
            conn.execute(sqlalchemy.text("SELECT 1"))
        print("[+] Database connection successful!")
    except Exception as e:
        print(f"[-] Connection failed: {e}")
        sys.exit(1)

    print("[*] Applying database migrations...")
    try:
        upgrade()
        print("[+] Alembic migrations applied successfully.")
    except Exception as e:
        print(f"[!] Migration warning (falling back to db.create_all()): {e}")
        db.create_all()
        print("[+] db.create_all() executed.")

    # Inspect created tables
    inspector = sqlalchemy.inspect(db.engine)
    tables = inspector.get_table_names()
    print(f"[+] Total tables found: {len(tables)}")
    print(f"    Tables: {', '.join(sorted(tables))}")
    print("\n[SUCCESS] Database is ready for production use!")
