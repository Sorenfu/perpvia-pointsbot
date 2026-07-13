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
    """Atomically check-and-deduct points for one user.

    Uses a Postgres transaction-scoped advisory lock keyed on discord_id so
    that two concurrent spends by the same user (e.g. double-clicking
    /redeem, or two devices at once) can't both read the same balance and
    both succeed, which would let a user go negative / redeem twice for the
    price of one.
    """
    amount = int(amount)
    if amount < 0:
        return False
    if amount == 0:
        return True

    discord_id = int(discord_id)
    async with db.transaction() as conn:
        # Advisory lock is released automatically at transaction end.
        await conn.execute("SELECT pg_advisory_xact_lock($1)", discord_id)
        balance = await conn.fetchval(
            "SELECT COALESCE(SUM(amount), 0) FROM points WHERE discord_id=$1", discord_id
        )
        if int(balance or 0) < amount:
            return False
        await conn.execute(
            "INSERT INTO points (discord_id, amount, type, reason) VALUES ($1, $2, $3, $4)",
            discord_id,
            -amount,
            "SHOP_PURCHASE",
            reason,
        )
    return True
