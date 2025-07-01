#!/usr/bin/env python3
"""
Database initialization script for Prediction Provider.
Creates the SQLite database and all required tables.
"""

import os
import sys
import sqlite3
from pathlib import Path

# Add the parent directory to the path to import app modules
sys.path.append(str(Path(__file__).parent.parent.parent))

from app.models import create_database_engine, create_tables, Base

def create_prediction_provider_database(db_path="prediction_provider.db"):
    """
    Create the prediction provider database with all required tables.
    
    Args:
        db_path (str): Path to the SQLite database file
    """
    try:
        # Create database directory if it doesn't exist
        db_dir = os.path.dirname(os.path.abspath(db_path))
        if db_dir and not os.path.exists(db_dir):
            os.makedirs(db_dir)
        
        # Create database engine
        database_url = f"sqlite:///{db_path}"
        print(f"Creating database at: {database_url}")
        
        engine = create_database_engine(database_url)
        
        # Create all tables
        print("Creating tables...")
        create_tables(engine)
        
        print("Database created successfully!")
        print(f"Database location: {os.path.abspath(db_path)}")
        
        # Verify tables were created
        with sqlite3.connect(db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
            tables = cursor.fetchall()
            print("Created tables:")
            for table in tables:
                print(f"  - {table[0]}")
        
        return True
        
    except Exception as e:
        print(f"Error creating database: {e}")
        return False

def main():
    """Main function to create the database."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Create Prediction Provider Database")
    parser.add_argument(
        "--db-path", 
        default="prediction_provider.db",
        help="Path to the SQLite database file (default: prediction_provider.db)"
    )
    
    args = parser.parse_args()
    
    success = create_prediction_provider_database(args.db_path)
    
    if success:
        print("\n✅ Database initialization completed successfully!")
        print("You can now start the Prediction Provider service.")
    else:
        print("\n❌ Database initialization failed!")
        sys.exit(1)

if __name__ == "__main__":
    main()
