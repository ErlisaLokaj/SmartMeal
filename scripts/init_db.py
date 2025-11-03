#!/usr/bin/env python3
"""
Standalone database initialization script
Can be run from host machine (outside Docker) or inside container
"""

import sys
import os

# Ensure we're using the right Python path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

# Import and run the init script
from scripts.init_databases import main

if __name__ == "__main__":
    print("\n" + "=" * 60)
    print("SmartMeal Database Initialization (Standalone)")
    print("=" * 60)
    print("\nThis will create/update:")
    print("  • PostgreSQL tables and schema")
    print("  • MongoDB collections and indexes")
    print("  • Neo4j constraints and seed data")
    print("\n" + "=" * 60 + "\n")

    exit_code = main()

    if exit_code == 0:
        print("\n" + "=" * 60)
        print("SUCCESS! Your databases are ready to use.")
        print("=" * 60)
        print("\nYou can now:")
        print("  • Access PostgreSQL at localhost:5432")
        print("  • Access MongoDB at localhost:27017")
        print("  • Access Neo4j Browser at http://localhost:7474")
        print("\n" + "=" * 60 + "\n")
    else:
        print("\n" + "=" * 60)
        print("FAILED! Check the errors above.")
        print("=" * 60 + "\n")

    sys.exit(exit_code)
