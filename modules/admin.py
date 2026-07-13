from __future__ import annotations

from config import OWNER_ID


def is_admin(discord_id: int) -> bool:
    return int(discord_id) == int(OWNER_ID)


async def log_admin(db, admin_discord_id: int, action: str, detail: str | None = None):
    await db.execute(
        "INSERT INTO admin_logs (admin_discord_id, action, detail) VALUES ($1, $2, $3)",
        int(admin_discord_id),
        action,
        detail,
    )
