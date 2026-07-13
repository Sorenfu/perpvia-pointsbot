from __future__ import annotations

from modules.points import get_balance, spend_points
from modules.reward import grant_role


async def list_products(db):
    return await db.fetch("SELECT * FROM products WHERE status='ACTIVE' ORDER BY id ASC")


async def create_product(db, name: str, price: int, role_id: int | None = None, description: str | None = None):
    return await db.fetchrow(
        "INSERT INTO products (name, price, role_id, description) VALUES ($1, $2, $3, $4) RETURNING *",
        name,
        int(price),
        int(role_id) if role_id else None,
        description,
    )


async def redeem_product(db, member, product_id: int):
    product = await db.fetchrow("SELECT * FROM products WHERE id=$1 AND status='ACTIVE'", int(product_id))
    if not product:
        return False, "Product not found"

    price = int(product["price"])
    if price > 0:
        balance = await get_balance(db, member.id)
        if balance < price:
            return False, f"Not enough points. Required: {price}, current: {balance}"

    # Grant the role (if any) BEFORE charging points. This avoids the bug
    # where a user is charged for a product but the role grant fails
    # (missing permission, deleted role, etc.) and they never get anything
    # for their points.
    role_ok, role_msg = await grant_role(member, product["role_id"])
    if not role_ok:
        return False, f"Redeem failed, nothing was charged: {role_msg}"

    if price > 0:
        ok = await spend_points(db, member.id, price, f"Redeemed product: {product['name']}")
        if not ok:
            return False, "Point deduction failed (your balance may have changed), please try again."

    await db.execute(
        "INSERT INTO orders (discord_id, product_id, price, status) VALUES ($1, $2, $3, 'SUCCESS')",
        int(member.id),
        int(product_id),
        price,
    )

    return True, f"Redeemed successfully. {role_msg}"
