from database import db
from modules import points, reward

async def get_products():
    return await db.fetch("SELECT * FROM products WHERE status='ACTIVE' ORDER BY id ASC")

async def create_product(name: str, price: int, role_id: int | None = None, description: str = ""):
    return await db.fetchrow(
        "INSERT INTO products(name, description, price, role_id, status) VALUES($1,$2,$3,$4,'ACTIVE') RETURNING *",
        name,
        description,
        price,
        role_id,
    )

async def redeem_product(member, user_id: int, product_id: int) -> tuple[bool, str, int]:
    product = await db.fetchrow("SELECT * FROM products WHERE id=$1 AND status='ACTIVE'", product_id)
    if not product:
        return False, "Product not found.", await points.get_balance(user_id)
    price = int(product["price"])
    try:
        balance_after = await points.spend_points(user_id, price, "SHOP_PURCHASE", product["name"])
    except ValueError as exc:
        if str(exc) == "INSUFFICIENT_POINTS":
            return False, f"Insufficient points. Need {price} points.", await points.get_balance(user_id)
        raise
    await db.execute(
        "INSERT INTO orders(user_id, product_id, price, status) VALUES($1,$2,$3,'SUCCESS')",
        user_id,
        product_id,
        price,
    )
    ok, role_msg = await reward.grant_role(member, product["role_id"])
    if not ok:
        return True, f"Redeemed, but role failed: {role_msg}", balance_after
    return True, f"Redeemed {product['name']}. {role_msg}", balance_after

async def get_orders(user_id: int):
    return await db.fetch(
        """
        SELECT o.*, p.name AS product_name
        FROM orders o
        JOIN products p ON p.id=o.product_id
        WHERE o.user_id=$1
        ORDER BY o.created_at DESC
        LIMIT 10
        """,
        user_id,
    )
