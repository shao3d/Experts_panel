"""Database initialization script."""

import sys
import os
from pathlib import Path

# Add parent directory to path for imports
sys.path.append(str(Path(__file__).parent.parent.parent))

from src.models.database import init_db, reset_db, drop_db


def main():
    """Initialize the database."""
    # Ensure data directory exists
    data_dir = Path(__file__).parent.parent.parent.parent / "data"
    data_dir.mkdir(exist_ok=True)

    print("Experts Panel Database Initialization")
    print("-" * 40)

    if len(sys.argv) > 1:
        command = sys.argv[1].lower()

        if command == "reset":
            confirm = input("⚠️  This will DELETE all data. Are you sure? (yes/no): ")
            if confirm.lower() == "yes":
                reset_db()
            else:
                print("Reset cancelled.")

        elif command == "drop":
            confirm = input("⚠️  This will DROP all tables. Are you sure? (yes/no): ")
            if confirm.lower() == "yes":
                drop_db()
            else:
                print("Drop cancelled.")

        else:
            print(f"Unknown command: {command}")
            print("Usage:")
            print("  python init_db.py        - Create tables (safe, won't drop existing)")
            print("  python init_db.py reset  - Drop and recreate all tables")
            print("  python init_db.py drop   - Drop all tables")
    else:
        # Default action: create tables (safe)
        init_db()
        print("\nTo reset the database, run: python init_db.py reset")


if __name__ == "__main__":
    main()