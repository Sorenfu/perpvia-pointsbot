from database import db

async def get_or_create_user(discord_user):
    row = await db.fetchrow("SELECT * FROM users WHERE discord_id=$1", discord_user.id)
    username = getattr(discord_user, "name", str(discord_user))
    if row:
        await db.execute("UPDATE users SET username=$1 WHERE discord_id=$2", username, discord_user.id)
        return await db.fetchrow("SELECT * FROM users WHERE discord_id=$1", discord_user.id)
    return await db.fetchrow(
        "INSERT INTO users(discord_id, username) VALUES($1, $2) RETURNING *",
        discord_user.id,
        username,
    )

async def get_user_by_discord_id(discord_id: int):
    return await db.fetchrow("SELECT * FROM users WHERE discord_id=$1", discord_id)

async def get_user_by_id(user_id: int):
    return await db.fetchrow("SELECT * FROM users WHERE id=$1", user_id)
