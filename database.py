from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path
import asyncpg


class Database:
    def __init__(self, database_url: str):
        self.database_url = database_url
        self.pool: asyncpg.Pool | None = None

    async def connect(self) -> None:
        self.pool = await asyncpg.create_pool(self.database_url, min_size=1, max_size=5)

    async def close(self) -> None:
        if self.pool:
            await self.pool.close()

    async def init_schema(self) -> None:
        sql_path = Path(__file__).with_name("init.sql")
        sql = sql_path.read_text(encoding="utf-8")
        async with self.pool.acquire() as conn:
            try:
                await conn.execute(sql)
            except asyncpg.exceptions.UndefinedColumnError as exc:
                raise RuntimeError(
                    "Schema init failed: one of the bot's tables already exists in "
                    "this Postgres database from an older/partial deployment, but "
                    "with different columns than this version expects "
                    "(CREATE TABLE IF NOT EXISTS skips tables that already exist, "
                    "so it never got fixed automatically). "
                    "Fix: open the Postgres service in Railway -> Query, run:\n"
                    "DROP TABLE IF EXISTS admin_logs, referrals, invite_codes, "
                    "orders, products, checkins, user_tasks, tasks, points, users "
                    "CASCADE;\n"
                    "then redeploy this service so init.sql recreates everything "
                    "fresh. Original error: "
                    f"{exc}"
                ) from exc

    async def execute(self, query: str, *args):
        async with self.pool.acquire() as conn:
            return await conn.execute(query, *args)

    async def fetch(self, query: str, *args):
        async with self.pool.acquire() as conn:
            return await conn.fetch(query, *args)

    async def fetchrow(self, query: str, *args):
        async with self.pool.acquire() as conn:
            return await conn.fetchrow(query, *args)

    async def fetchval(self, query: str, *args):
        async with self.pool.acquire() as conn:
            return await conn.fetchval(query, *args)

    @asynccontextmanager
    async def transaction(self):
        """Acquire a connection and open a DB transaction on it.

        Use this whenever a series of statements must be applied atomically
        (e.g. read-balance-then-write flows) so that concurrent requests
        can't interleave and cause double-spend style bugs.
        """
        async with self.pool.acquire() as conn:
            async with conn.transaction():
                yield conn
