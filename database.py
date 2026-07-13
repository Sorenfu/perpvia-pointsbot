import asyncpg
from pathlib import Path
from config import DATABASE_URL

class Database:
    def __init__(self):
        self.pool: asyncpg.Pool | None = None

    async def connect(self) -> None:
        if not DATABASE_URL:
            raise RuntimeError("DATABASE_URL is not configured")
        self.pool = await asyncpg.create_pool(dsn=DATABASE_URL, min_size=1, max_size=8)

    async def close(self) -> None:
        if self.pool:
            await self.pool.close()

    async def init_schema(self) -> None:
        sql = Path("init.sql").read_text(encoding="utf-8")
        await self.execute(sql)

    async def execute(self, query: str, *args):
        if not self.pool:
            raise RuntimeError("Database is not connected")
        async with self.pool.acquire() as conn:
            return await conn.execute(query, *args)

    async def fetch(self, query: str, *args):
        if not self.pool:
            raise RuntimeError("Database is not connected")
        async with self.pool.acquire() as conn:
            return await conn.fetch(query, *args)

    async def fetchrow(self, query: str, *args):
        if not self.pool:
            raise RuntimeError("Database is not connected")
        async with self.pool.acquire() as conn:
            return await conn.fetchrow(query, *args)

    async def fetchval(self, query: str, *args):
        if not self.pool:
            raise RuntimeError("Database is not connected")
        async with self.pool.acquire() as conn:
            return await conn.fetchval(query, *args)

    async def transaction(self):
        if not self.pool:
            raise RuntimeError("Database is not connected")
        conn = await self.pool.acquire()
        tx = conn.transaction()
        await tx.start()
        return conn, tx

db = Database()
