"""
connection.py
-------------
Manages the global aiomysql connection pool.

The pool is created lazily on the first call to ``get_pool()`` and is
closed explicitly via ``close_pool()``.  In production the pool is
created during the FastAPI lifespan handler so it is always available
before any request is handled.
"""
import os

import aiomysql

# Module-level singleton — None until get_pool() is first called.
_pool = None


async def get_pool() -> aiomysql.Pool:
    """
    Return the shared connection pool, creating it on the first call.

    Pool settings are read from environment variables:
        MYSQL_HOST      (default: "localhost")
        MYSQL_PORT      (default: 3306)
        MYSQL_USER
        MYSQL_PASSWORD
        MYSQL_DATABASE  (default: "agent_db")
    """
    global _pool
    if _pool is None:
        _pool = await aiomysql.create_pool(
            host=os.getenv("MYSQL_HOST", "localhost"),
            port=int(os.getenv("MYSQL_PORT", 3306)),
            user=os.getenv("MYSQL_USER"),
            password=os.getenv("MYSQL_PASSWORD"),
            db=os.getenv("MYSQL_DATABASE", "agent_db"),
            minsize=5,
            maxsize=20,
            autocommit=True,
        )
    return _pool


async def close_pool() -> None:
    """
    Gracefully shut down the connection pool.

    Safe to call even if the pool was never opened.  After this call
    ``get_pool()`` will create a fresh pool on the next invocation.
    """
    global _pool
    if _pool is not None:
        _pool.close()
        await _pool.wait_closed()
        _pool = None
