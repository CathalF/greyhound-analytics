"""
Database connection and query management.

Provides connection pooling for PostgreSQL using psycopg2 with configuration
from environment variables.
"""

import os
from contextlib import contextmanager
from typing import Optional, List, Tuple, Any

import psycopg2
from psycopg2 import pool
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()


class Database:
    """
    Database connection manager with connection pooling.

    Uses ThreadedConnectionPool to maintain a pool of database connections
    for efficient resource usage. Reads DATABASE_URL from environment.
    """

    def __init__(self):
        """Initialize connection pool from DATABASE_URL environment variable."""
        database_url = os.getenv('DATABASE_URL')

        if not database_url:
            raise ValueError(
                "DATABASE_URL not found in environment. "
                "Please copy .env.example to .env and configure your database connection."
            )

        try:
            self.pool = psycopg2.pool.ThreadedConnectionPool(
                minconn=1,
                maxconn=10,
                dsn=database_url
            )
        except psycopg2.Error as e:
            raise ConnectionError(f"Failed to create connection pool: {e}")

    @contextmanager
    def get_connection(self):
        """
        Get a connection from the pool using context manager.

        Yields:
            psycopg2 connection object

        Example:
            with db.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT * FROM races")
                    results = cur.fetchall()
        """
        conn = self.pool.getconn()
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            self.pool.putconn(conn)

    def execute_query(
        self,
        query: str,
        params: Optional[Tuple[Any, ...]] = None,
        fetch: bool = True
    ) -> Optional[List[Any]]:
        """
        Execute a parameterized SQL query safely.

        Args:
            query: SQL query with %s placeholders for parameters
            params: Tuple of parameters to substitute into query
            fetch: Whether to fetch and return results (SELECT queries)

        Returns:
            List of results if fetch=True, None otherwise

        Example:
            # Insert
            db.execute_query(
                "INSERT INTO races (name, track) VALUES (%s, %s)",
                ("Race 1", "Romford"),
                fetch=False
            )

            # Select
            results = db.execute_query(
                "SELECT * FROM races WHERE track = %s",
                ("Romford",)
            )
        """
        with self.get_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(query, params)

                if fetch:
                    return cur.fetchall()
                return None

    def close(self):
        """Close all connections in the pool."""
        if hasattr(self, 'pool') and self.pool:
            self.pool.closeall()


# Global database instance
_db_instance: Optional[Database] = None


def get_db() -> Database:
    """
    Get or create the global database instance.

    Returns:
        Database instance with connection pooling

    Example:
        from src.storage.db import get_db

        db = get_db()
        races = db.execute_query("SELECT * FROM races")
    """
    global _db_instance

    if _db_instance is None:
        _db_instance = Database()

    return _db_instance
