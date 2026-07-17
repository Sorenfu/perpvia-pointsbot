from __future__ import annotations

from modules.points import get_balance, spend_points
from modules.reward import grant_role


async def list_products(db):
    return await db.fetch("SELECT * FROM products WHERE status='ACTIVE' ORDER BY id ASC")


async def list_all_products(db):
    return await db.fetch("SELECT * FROM products ORDER BY id ASC")


async def get_product(db, product_id: int):
    return await db.fetchrow("SELECT * FROM products WHERE id=$1 AND status='ACTIVE'", int(product_id))


async def create_product(
    db,
    name: str,
    price: int,
    role_id: int | None = None,
    description: str | None = None,
    stock: int | None = None,
    requires_wallet: bool = False,
):
    return await db.fetchrow(
        '''
        INSERT INTO products (name, price, role_id, description, stock, requires_wallet)
        VALUES ($1, $2, $3, $4, $5, $6)
        RETURNING *
        ''',
        name,
        int(price),
        int(role_id) if role_id else None,
        description,
        int(stock) if stock is not None else None,
        bool(requires_wallet),
    )


async def edit_product(
    db,
    product_id: int,
    name: str,
    price: int,
    role_id: int | None = None,
    description: str | None = None,
    stock: int | None = None,
    requires_wallet: bool = False,
):
    return await db.fetchrow(
        '''
        UPDATE products
        SET name=$2, price=$3, role_id=$4, description=$5, stock=$6, requires_wallet=$7
        WHERE id=$1 AND status='ACTIVE'
        RETURNING *
        ''',
        int(product_id),
        name,
        int(price),
        int(role_id) if role_id else None,
        description,
        int(stock) if stock is not None else None,
        bool(requires_wallet),
    )


async def remove_product(db, product_id: int):
    return await db.fetchrow(
        "UPDATE products SET status='INACTIVE' WHERE id=$1 AND status='ACTIVE' RETURNING *",
        int(product_id),
    )


async def has_redeemed(db, discord_id: int, product_id: int) -> bool:
    row = await db.fetchrow(
        "SELECT id FROM orders WHERE discord_id=$1 AND product_id=$2",
        int(discord_id),
        int(product_id),
    )
    return row is not None


async def get_redeemed_product_ids(db, discord_id: int) -> set[int]:
    rows = await db.fetch("SELECT product_id FROM orders WHERE discord_id=$1", int(discord_id))
    return {int(r["product_id"]) for r in rows}


async def redeem_product(
    db, member, product_id: int, wallet_address: str | None = None, wallet_verified: bool | None = None
):
    async with db.transaction() as conn:
        product = await conn.fetchrow(
            "SELECT * FROM products WHERE id=$1 AND status='ACTIVE' FOR UPDATE",
            int(product_id),
        )
        if not product:
            return False, "Product not found"

        already = await conn.fetchrow(
            "SELECT id FROM orders WHERE discord_id=$1 AND product_id=$2",
            int(member.id),
            int(product_id),
        )
        if already:
            return False, "You have already redeemed this product. Each product can only be redeemed once per user."

        if product["stock"] is not None and int(product["stock"]) <= 0:
            return False, "This product is sold out."

        balance = await get_balance(conn, member.id)
        price = int(product["price"])
        if balance < price:
            return False, f"Not enough points. Required: {price}, current: {balance}"

        ok = await spend_points(conn, member.id, price, f"Redeemed product: {product['name']}")
        if not ok:
            return False, "Point deduction failed"

        await conn.execute(
            '''
            INSERT INTO orders (discord_id, product_id, price, status, wallet_address, wallet_verified)
            VALUES ($1, $2, $3, 'SUCCESS', $4, $5)
            ''',
            int(member.id),
            int(product_id),
            price,
            wallet_address,
            wallet_verified,
        )

        if product["stock"] is not None:
            await conn.execute(
                "UPDATE products SET stock = stock - 1 WHERE id=$1",
                int(product_id),
            )

    role_ok, role_msg = await grant_role(member, product["role_id"])
    if not role_ok:
        return True, f"Redeemed, but role warning: {role_msg}"

    return True, f"Redeemed successfully. {role_msg}"


async def export_orders(db):
    """Full redemption history for statistics/export, including the wallet snapshot at redemption time."""
    return await db.fetch(
        '''
        SELECT
            o.id AS order_id,
            o.discord_id,
            u.username,
            o.product_id,
            p.name AS product_name,
            o.price,
            o.status,
            o.wallet_address,
            o.wallet_verified,
            o.created_at
        FROM orders o
        LEFT JOIN products p ON p.id = o.product_id
        LEFT JOIN users u ON u.discord_id = o.discord_id
        ORDER BY o.id ASC
        '''
    )
