from __future__ import annotations

import discord

from config import OWNER_ID, ADMIN_ROLE_ID


def is_admin(user: discord.abc.User) -> bool:
    if int(user.id) == int(OWNER_ID):
        return True
    if ADMIN_ROLE_ID and isinstance(user, discord.Member):
        return any(role.id == ADMIN_ROLE_ID for role in user.roles)
    return False


async def log_admin(db, admin_discord_id: int, action: str, detail: str | None = None):
    await db.execute(
        "INSERT INTO admin_logs (admin_discord_id, action, detail) VALUES ($1, $2, $3)",
        int(admin_discord_id),
        action,
        detail,
    )
