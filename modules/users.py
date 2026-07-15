from __future__ import annotations

import discord


async def ensure_user(db, discord_user: discord.abc.User):
    username = getattr(discord_user, "display_name", None) or getattr(discord_user, "name", str(discord_user.id))
    await db.execute(
        '''
        INSERT INTO users (discord_id, username)
        VALUES ($1, $2)
        ON CONFLICT (discord_id)
        DO UPDATE SET username = EXCLUDED.username
        ''',
        int(discord_user.id),
        username,
    )
    return await db.fetchrow("SELECT * FROM users WHERE discord_id=$1", int(discord_user.id))


async def get_user(db, discord_id: int):
    return await db.fetchrow("SELECT * FROM users WHERE discord_id=$1", int(discord_id))
