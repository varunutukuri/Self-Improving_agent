import aiomysql
import os

_pool = None

async def get_pool():
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

async def close_pool():
    global _pool
    if _pool:
        _pool.close()
        await _pool.wait_closed()
        _pool = None
