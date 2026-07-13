from database import db

async def get_balance(user_id: int) -> int:
    value = await db.fetchval("SELECT COALESCE(SUM(amount), 0) FROM points WHERE user_id=$1", user_id)
    return int(value or 0)

async def add_points(user_id: int, amount: int, point_type: str, reason: str = "") -> int:
    if amount <= 0:
        raise ValueError("amount must be positive")
    await db.execute(
        "INSERT INTO points(user_id, amount, type, reason) VALUES($1, $2, $3, $4)",
        user_id,
        amount,
        point_type,
        reason,
    )
    return await get_balance(user_id)

async def spend_points(user_id: int, amount: int, point_type: str, reason: str = "") -> int:
    if amount <= 0:
        raise ValueError("amount must be positive")
    balance = await get_balance(user_id)
    if balance < amount:
        raise ValueError("INSUFFICIENT_POINTS")
    await db.execute(
        "INSERT INTO points(user_id, amount, type, reason) VALUES($1, $2, $3, $4)",
        user_id,
        -amount,
        point_type,
        reason,
    )
    return await get_balance(user_id)
