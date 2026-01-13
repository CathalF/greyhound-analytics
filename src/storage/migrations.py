"""
Database migration helper.

Executes schema.sql to create or update database tables. Reads DATABASE_URL
from environment and applies the schema with proper error handling.
"""

import os
import sys
from pathlib import Path

import psycopg2
from psycopg2 import sql
from dotenv import load_dotenv

# Load environment variables
load_dotenv()


def run_migrations() -> bool:
    """
    Execute database schema migrations from schema.sql file.
    
    Reads DATABASE_URL from environment, connects to PostgreSQL,
    executes schema.sql DDL statements, and commits the transaction.
    
    Returns:
        True if migrations succeeded, False otherwise
        
    Raises:
        ValueError: If DATABASE_URL not found in environment
        FileNotFoundError: If schema.sql file doesn't exist
    """
    # Get database URL from environment
    database_url = os.getenv('DATABASE_URL')
    
    if not database_url:
        raise ValueError(
            "DATABASE_URL not found in environment. "
            "Please copy .env.example to .env and configure your database connection."
        )
    
    # Get schema.sql file path (same directory as this file)
    schema_path = Path(__file__).parent / 'schema.sql'
    
    if not schema_path.exists():
        raise FileNotFoundError(f"Schema file not found at {schema_path}")
    
    # Read schema SQL
    print(f"Reading schema from {schema_path}...")
    with open(schema_path, 'r') as f:
        schema_sql = f.read()
    
    # Connect to database and execute migrations
    conn = None
    try:
        print(f"Connecting to database...")
        conn = psycopg2.connect(database_url)
        
        with conn.cursor() as cur:
            print("Executing schema migrations...")
            cur.execute(schema_sql)
        
        # Commit the transaction
        conn.commit()
        print("✓ Migrations completed successfully!")
        return True
        
    except psycopg2.Error as e:
        print(f"✗ Migration failed: {e}", file=sys.stderr)
        
        if conn:
            conn.rollback()
            print("Transaction rolled back.", file=sys.stderr)
        
        return False
        
    finally:
        if conn:
            conn.close()
            print("Database connection closed.")


if __name__ == '__main__':
    """
    Run migrations when executed as a script.
    
    Usage:
        python -m src.storage.migrations
    """
    print("=" * 60)
    print("Database Migration Tool")
    print("=" * 60)
    
    try:
        success = run_migrations()
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"✗ Error: {e}", file=sys.stderr)
        sys.exit(1)
