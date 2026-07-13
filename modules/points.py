from __future__ import annotations


async def get_balance(db, discord_id: int) -> int:
    value = await db.fetchval("SELECT COALESCE(SUM(amount), 0) FROM points WHERE discord_id=$1", int(discord_id))
    return int(value or 0)


async def add_points(db, discord_id: int, amount: int, point_type: str, reason: str | None = None) -> None:
    if amount == 0:
        return
    await db.execute(
        "INSERT INTO points (discord_id, amount, type, reason) VALUES ($1, $2, $3, $4)",
        int(discord_id),
        int(amount),
        point_type,
        reason,
    )


async def spend_points(db, discord_id: int, amount: int, reason: str | None = None) -> bool:
    amount = int(amount)
    if amount <= 0:
        return False
    balance = await get_balance(db, discord_id)
    if balance < amount:
        return False
    await add_points(db, discord_id, -amount, "SHOP_PURCHASE", reason)
    return True
