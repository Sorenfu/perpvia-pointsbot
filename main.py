import os
import asyncio
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, Tuple

import discord
from discord import app_commands
from dotenv import load_dotenv
import asyncpg
import redis.asyncio as redis

load_dotenv()

# =========================
# Basic Config
# =========================
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
GUILD_ID = int(os.getenv("GUILD_ID", "0"))
DATABASE_URL = os.getenv("DATABASE_URL")
REDIS_URL = os.getenv("REDIS_URL")
ADMIN_USER_IDS = {
    int(x.strip()) for x in os.getenv("ADMIN_USER_IDS", "").split(",") if x.strip().isdigit()
}

SHOP_CHANNEL_ID = int(os.getenv("SHOP_CHANNEL_ID", "1519929709914493018"))
POINT_LOG_CHANNEL_ID = int(os.getenv("POINT_LOG_CHANNEL_ID", "1524658027716804648"))
ADMIN_LOG_CHANNEL_ID = int(os.getenv("ADMIN_LOG_CHANNEL_ID", "1524658027716804648"))
CAMPAIGN_CHANNEL_ID = int(os.getenv("CAMPAIGN_CHANNEL_ID", "1501804167201689661"))
ANNOUNCEMENT_CHANNEL_ID = int(os.getenv("ANNOUNCEMENT_CHANNEL_ID", "1501779720449294406"))

DAILY_REWARD = 20
DAILY_COOLDOWN_HOURS = 12
MESSAGE_REWARD = 1
MESSAGE_COOLDOWN_SECONDS = 60
MESSAGE_MIN_LENGTH = 10
MESSAGE_DAILY_LIMIT = 50
INVITE_REWARD = 20

ROLE_REWARDS = {
    1506518512179351612: ("Pathfinder", 100),
    1506518516592017418: ("Trailblazer", 300),
    1506518516679839855: ("Momentum Maker", 500),
    1506518520660234323: ("Via Elite", 1000),
}

# =========================
# Runtime State
# =========================
db_pool: Optional[asyncpg.Pool] = None
redis_client: Optional[redis.Redis] = None
memory_cooldowns: Dict[int, datetime] = {}

# =========================
# Database
# =========================
SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS users (
    discord_id BIGINT PRIMARY KEY,
    points BIGINT NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS point_transactions (
    id BIGSERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL,
    amount BIGINT NOT NULL,
    source TEXT NOT NULL,
    reason TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS daily_checkins (
    id BIGSERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL,
    reward BIGINT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS message_rewards (
    id BIGSERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL,
    amount BIGINT NOT NULL,
    reward_date DATE NOT NULL DEFAULT CURRENT_DATE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS invites (
    id BIGSERIAL PRIMARY KEY,
    inviter_id BIGINT NOT NULL,
    invitee_id BIGINT NOT NULL UNIQUE,
    invite_code TEXT,
    status TEXT NOT NULL DEFAULT 'pending',
    reward_claimed BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    verified_at TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS role_reward_history (
    id BIGSERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL,
    role_id BIGINT NOT NULL,
    role_name TEXT,
    reward BIGINT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(user_id, role_id)
);

CREATE TABLE IF NOT EXISTS products (
    id BIGSERIAL PRIMARY KEY,
    name TEXT NOT NULL,
    description TEXT DEFAULT '',
    price BIGINT NOT NULL,
    product_type TEXT NOT NULL DEFAULT 'ITEM',
    role_id BIGINT,
    stock INT NOT NULL DEFAULT -1,
    status TEXT NOT NULL DEFAULT 'active',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS orders (
    id BIGSERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL,
    product_id BIGINT NOT NULL,
    cost BIGINT NOT NULL,
    status TEXT NOT NULL DEFAULT 'created',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS audit_logs (
    id BIGSERIAL PRIMARY KEY,
    operator_id BIGINT,
    action TEXT NOT NULL,
    target_id BIGINT,
    payload TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
"""

async def init_database() -> None:
    global db_pool
    if not DATABASE_URL:
        raise RuntimeError("DATABASE_URL is missing")
    db_pool = await asyncpg.create_pool(DATABASE_URL, min_size=1, max_size=5)
    async with db_pool.acquire() as conn:
        await conn.execute(SCHEMA_SQL)
        count = await conn.fetchval("SELECT COUNT(*) FROM products")
        if count == 0:
            await conn.execute(
                """
                INSERT INTO products(name, description, price, product_type, stock, status)
                VALUES
                ('VIP Membership', 'Role product. Configure role_id later if needed.', 1000, 'ROLE', -1, 'active'),
                ('Genesis Pass', 'NFT style pass placeholder.', 5000, 'NFT', -1, 'active')
                """
            )
    print("Database Connected and Schema Ready")

async def init_redis() -> None:
    global redis_client
    if not REDIS_URL:
        print("Redis URL missing, using in-memory cooldown fallback")
        return
    try:
        redis_client = redis.from_url(REDIS_URL, decode_responses=True)
        await redis_client.ping()
        print("Redis Connected")
    except Exception as exc:
        redis_client = None
        print(f"Redis unavailable, using memory fallback: {exc}")

# =========================
# Point Engine
# =========================
async def ensure_user(user_id: int) -> None:
    async with db_pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO users(discord_id, points)
            VALUES($1, 0)
            ON CONFLICT(discord_id) DO NOTHING
            """,
            user_id,
        )

async def get_balance(user_id: int) -> int:
    await ensure_user(user_id)
    async with db_pool.acquire() as conn:
        points = await conn.fetchval("SELECT points FROM users WHERE discord_id=$1", user_id)
    return int(points or 0)

async def add_points(user_id: int, amount: int, source: str, reason: str) -> int:
    await ensure_user(user_id)
    async with db_pool.acquire() as conn:
        async with conn.transaction():
            points = await conn.fetchval(
                """
                UPDATE users
                SET points = points + $2, updated_at = NOW()
                WHERE discord_id=$1
                RETURNING points
                """,
                user_id,
                amount,
            )
            await conn.execute(
                """
                INSERT INTO point_transactions(user_id, amount, source, reason)
                VALUES($1, $2, $3, $4)
                """,
                user_id,
                amount,
                source,
                reason,
            )
    return int(points or 0)

async def spend_points(user_id: int, amount: int, source: str, reason: str) -> Tuple[bool, int]:
    await ensure_user(user_id)
    async with db_pool.acquire() as conn:
        async with conn.transaction():
            current = await conn.fetchval("SELECT points FROM users WHERE discord_id=$1 FOR UPDATE", user_id)
            current = int(current or 0)
            if current < amount:
                return False, current
            new_balance = current - amount
            await conn.execute("UPDATE users SET points=$2, updated_at=NOW() WHERE discord_id=$1", user_id, new_balance)
            await conn.execute(
                "INSERT INTO point_transactions(user_id, amount, source, reason) VALUES($1, $2, $3, $4)",
                user_id,
                -amount,
                source,
                reason,
            )
            return True, new_balance

async def log_to_channel(channel_id: int, message: str) -> None:
    channel = bot.get_channel(channel_id)
    if channel:
        try:
            await channel.send(message)
        except Exception as exc:
            print(f"Failed sending log to {channel_id}: {exc}")

# =========================
# Daily
# =========================
async def handle_daily(user_id: int) -> Tuple[bool, str]:
    now = datetime.now(timezone.utc)
    async with db_pool.acquire() as conn:
        last = await conn.fetchrow(
            """
            SELECT created_at FROM daily_checkins
            WHERE user_id=$1
            ORDER BY created_at DESC
            LIMIT 1
            """,
            user_id,
        )
    if last and now - last["created_at"] < timedelta(hours=DAILY_COOLDOWN_HOURS):
        remaining = timedelta(hours=DAILY_COOLDOWN_HOURS) - (now - last["created_at"])
        hours = int(remaining.total_seconds() // 3600)
        minutes = int((remaining.total_seconds() % 3600) // 60)
        return False, f"⏳ Daily cooldown active. Try again in {hours}h {minutes}m."

    balance = await add_points(user_id, DAILY_REWARD, "daily", "Daily Check-in")
    async with db_pool.acquire() as conn:
        await conn.execute(
            "INSERT INTO daily_checkins(user_id, reward) VALUES($1, $2)",
            user_id,
            DAILY_REWARD,
        )
    await resolve_invite_reward_if_needed(user_id)
    await log_to_channel(POINT_LOG_CHANNEL_ID, f"🎉 Daily Reward | <@{user_id}> +{DAILY_REWARD} Points | Balance: {balance}")
    return True, f"🎉 Daily +{DAILY_REWARD} Points\n💎 Balance: {balance} Points"

# =========================
# Message Reward
# =========================
async def can_reward_message(user_id: int) -> bool:
    now = datetime.now(timezone.utc)
    key = f"message_reward:last:{user_id}"
    if redis_client:
        exists = await redis_client.get(key)
        if exists:
            return False
        await redis_client.setex(key, MESSAGE_COOLDOWN_SECONDS, "1")
        return True
    last = memory_cooldowns.get(user_id)
    if last and (now - last).total_seconds() < MESSAGE_COOLDOWN_SECONDS:
        return False
    memory_cooldowns[user_id] = now
    return True

async def reward_message_if_valid(message: discord.Message) -> None:
    if message.author.bot:
        return
    if len(message.content.strip()) < MESSAGE_MIN_LENGTH:
        return
    user_id = message.author.id
    if not await can_reward_message(user_id):
        return
    async with db_pool.acquire() as conn:
        earned_today = await conn.fetchval(
            """
            SELECT COALESCE(SUM(amount), 0)
            FROM message_rewards
            WHERE user_id=$1 AND reward_date=CURRENT_DATE
            """,
            user_id,
        )
    if int(earned_today or 0) >= MESSAGE_DAILY_LIMIT:
        return
    await add_points(user_id, MESSAGE_REWARD, "message", "Message Reward")
    async with db_pool.acquire() as conn:
        await conn.execute(
            "INSERT INTO message_rewards(user_id, amount) VALUES($1, $2)",
            user_id,
            MESSAGE_REWARD,
        )

# =========================
# Invite Reward
# =========================
async def resolve_invite_reward_if_needed(invitee_id: int) -> None:
    async with db_pool.acquire() as conn:
        invite = await conn.fetchrow(
            """
            SELECT id, inviter_id, reward_claimed
            FROM invites
            WHERE invitee_id=$1 AND reward_claimed=FALSE
            LIMIT 1
            """,
            invitee_id,
        )
        if not invite:
            return
        async with conn.transaction():
            await conn.execute(
                """
                UPDATE invites
                SET status='verified', reward_claimed=TRUE, verified_at=NOW()
                WHERE id=$1 AND reward_claimed=FALSE
                """,
                invite["id"],
            )
    inviter_id = int(invite["inviter_id"])
    balance = await add_points(inviter_id, INVITE_REWARD, "invite", f"Invite reward for {invitee_id}")
    await log_to_channel(POINT_LOG_CHANNEL_ID, f"🤝 Invite Reward | <@{inviter_id}> +{INVITE_REWARD} Points | Invitee: <@{invitee_id}> | Balance: {balance}")

async def refresh_invite_cache(guild: discord.Guild) -> None:
    try:
        invites = await guild.invites()
        bot.invite_cache[guild.id] = {i.code: (i.uses or 0, i.inviter.id if i.inviter else None) for i in invites}
        print(f"Invite cache refreshed for {guild.name}")
    except Exception as exc:
        print(f"Invite cache unavailable. Need Manage Server permission for accurate invite rewards: {exc}")

async def track_member_invite(member: discord.Member) -> None:
    guild = member.guild
    old = bot.invite_cache.get(guild.id, {})
    try:
        new_invites = await guild.invites()
    except Exception as exc:
        print(f"Cannot read invites on member join: {exc}")
        return
    used_code = None
    inviter_id = None
    for inv in new_invites:
        old_uses, old_inviter = old.get(inv.code, (0, inv.inviter.id if inv.inviter else None))
        if (inv.uses or 0) > old_uses:
            used_code = inv.code
            inviter_id = inv.inviter.id if inv.inviter else old_inviter
            break
    bot.invite_cache[guild.id] = {i.code: (i.uses or 0, i.inviter.id if i.inviter else None) for i in new_invites}
    if inviter_id and inviter_id != member.id:
        async with db_pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO invites(inviter_id, invitee_id, invite_code, status)
                VALUES($1, $2, $3, 'pending')
                ON CONFLICT(invitee_id) DO NOTHING
                """,
                inviter_id,
                member.id,
                used_code,
            )
        await log_to_channel(POINT_LOG_CHANNEL_ID, f"🧩 Invite Tracked | Inviter: <@{inviter_id}> | New user: <@{member.id}> | Reward after first /daily")

# =========================
# Role Reward
# =========================
async def reward_roles(before: discord.Member, after: discord.Member) -> None:
    before_ids = {r.id for r in before.roles}
    after_ids = {r.id for r in after.roles}
    added = after_ids - before_ids
    for role_id in added:
        if role_id not in ROLE_REWARDS:
            continue
        role_name, reward = ROLE_REWARDS[role_id]
        async with db_pool.acquire() as conn:
            try:
                await conn.execute(
                    """
                    INSERT INTO role_reward_history(user_id, role_id, role_name, reward)
                    VALUES($1, $2, $3, $4)
                    """,
                    after.id,
                    role_id,
                    role_name,
                    reward,
                )
            except asyncpg.UniqueViolationError:
                continue
        balance = await add_points(after.id, reward, "role_reward", f"Role reward: {role_name}")
        await log_to_channel(POINT_LOG_CHANNEL_ID, f"🏅 Role Reward | <@{after.id}> +{reward} Points | {role_name} | Balance: {balance}")

# =========================
# Shop
# =========================
class RedeemView(discord.ui.View):
    def __init__(self, products):
        super().__init__(timeout=180)
        for product in products[:25]:
            button = discord.ui.Button(
                label=f"Redeem #{product['id']}",
                style=discord.ButtonStyle.primary,
                custom_id=f"redeem:{product['id']}",
            )
            button.callback = self.make_callback(product["id"])
            self.add_item(button)

    def make_callback(self, product_id: int):
        async def callback(interaction: discord.Interaction):
            await redeem_product(interaction, product_id)
        return callback

async def get_products():
    async with db_pool.acquire() as conn:
        return await conn.fetch(
            """
            SELECT id, name, description, price, product_type, role_id, stock
            FROM products
            WHERE status='active'
            ORDER BY id ASC
            LIMIT 25
            """
        )

async def redeem_product(interaction: discord.Interaction, product_id: int) -> None:
    await interaction.response.defer(ephemeral=True)
    async with db_pool.acquire() as conn:
        product = await conn.fetchrow(
            "SELECT id, name, price, product_type, role_id, stock FROM products WHERE id=$1 AND status='active'",
            product_id,
        )
    if not product:
        await interaction.followup.send("This product is not available.", ephemeral=True)
        return
    if product["stock"] == 0:
        await interaction.followup.send("This product is out of stock.", ephemeral=True)
        return
    ok, new_balance = await spend_points(interaction.user.id, int(product["price"]), "shop", f"Redeem {product['name']}")
    if not ok:
        await interaction.followup.send(f"Not enough points. Current balance: {new_balance} Points", ephemeral=True)
        return
    async with db_pool.acquire() as conn:
        order_id = await conn.fetchval(
            "INSERT INTO orders(user_id, product_id, cost, status) VALUES($1, $2, $3, 'created') RETURNING id",
            interaction.user.id,
            product_id,
            int(product["price"]),
        )
        if product["stock"] and product["stock"] > 0:
            await conn.execute("UPDATE products SET stock=stock-1 WHERE id=$1", product_id)

    delivered = False
    if product["product_type"].upper() == "ROLE" and product["role_id"]:
        role = interaction.guild.get_role(int(product["role_id"])) if interaction.guild else None
        if role and isinstance(interaction.user, discord.Member):
            try:
                await interaction.user.add_roles(role, reason=f"Shop redeem order #{order_id}")
                delivered = True
                async with db_pool.acquire() as conn:
                    await conn.execute("UPDATE orders SET status='delivered' WHERE id=$1", order_id)
            except Exception as exc:
                print(f"Role delivery failed: {exc}")
    await log_to_channel(POINT_LOG_CHANNEL_ID, f"🛒 Shop Redeem | <@{interaction.user.id}> spent {product['price']} Points | {product['name']} | Order #{order_id}")
    status = "Delivered" if delivered else "Order created. Admin will process it."
    await interaction.followup.send(f"✅ Redeemed: {product['name']}\nCost: {product['price']} Points\nBalance: {new_balance} Points\n{status}", ephemeral=True)

# =========================
# Admin Helpers
# =========================
def is_admin(user_id: int) -> bool:
    return user_id in ADMIN_USER_IDS

async def audit(operator_id: int, action: str, target_id: Optional[int] = None, payload: str = "") -> None:
    async with db_pool.acquire() as conn:
        await conn.execute(
            "INSERT INTO audit_logs(operator_id, action, target_id, payload) VALUES($1, $2, $3, $4)",
            operator_id,
            action,
            target_id,
            payload,
        )
    await log_to_channel(ADMIN_LOG_CHANNEL_ID, f"🛠 Admin Action | <@{operator_id}> | {action} | Target: {target_id or '-'} | {payload}")

# =========================
# Discord Client
# =========================
class CommunityOS(discord.Client):
    def __init__(self):
        intents = discord.Intents.default()
        intents.members = True
        intents.message_content = True
        super().__init__(intents=intents)
        self.tree = app_commands.CommandTree(self)
        self.invite_cache: Dict[int, Dict[str, Tuple[int, Optional[int]]]] = {}

    async def setup_hook(self):
        print("Community OS Starting")
        await init_database()
        await init_redis()
        guild = discord.Object(id=GUILD_ID)
        # Hard reset guild commands to avoid old command registry residue.
        self.tree.clear_commands(guild=guild)
        await self.tree.sync(guild=guild)
        self.tree.copy_global_to(guild=guild)
        synced = await self.tree.sync(guild=guild)
        print("Synced Commands:", [cmd.name for cmd in synced])

bot = CommunityOS()

# =========================
# Commands
# =========================
@bot.tree.command(name="balance", description="View your points balance")
async def balance(interaction: discord.Interaction):
    points = await get_balance(interaction.user.id)
    await interaction.response.send_message(f"💎 Balance: {points} Points", ephemeral=True)

@bot.tree.command(name="daily", description="Claim daily points")
async def daily(interaction: discord.Interaction):
    ok, message = await handle_daily(interaction.user.id)
    await interaction.response.send_message(message, ephemeral=True)

@bot.tree.command(name="shop", description="Open the point shop")
async def shop(interaction: discord.Interaction):
    products = await get_products()
    if not products:
        await interaction.response.send_message("Shop is empty.", ephemeral=True)
        return
    embed = discord.Embed(title="🛒 Point Shop", description="Use your points to redeem rewards.", color=0x00AEEF)
    for p in products:
        stock = "Unlimited" if p["stock"] == -1 else str(p["stock"])
        embed.add_field(
            name=f"#{p['id']} {p['name']} - {p['price']} Points",
            value=f"Type: {p['product_type']}\nStock: {stock}\n{p['description'] or ''}",
            inline=False,
        )
    await interaction.response.send_message(embed=embed, view=RedeemView(products), ephemeral=True)

@bot.tree.command(name="leaderboard", description="Show top point holders")
async def leaderboard(interaction: discord.Interaction):
    async with db_pool.acquire() as conn:
        rows = await conn.fetch("SELECT discord_id, points FROM users ORDER BY points DESC LIMIT 10")
    if not rows:
        await interaction.response.send_message("No users yet.", ephemeral=True)
        return
    lines = [f"{idx+1}. <@{r['discord_id']}> - {r['points']} Points" for idx, r in enumerate(rows)]
    await interaction.response.send_message("🏆 Leaderboard\n" + "\n".join(lines), ephemeral=False)

@bot.tree.command(name="add_points", description="Admin: add points to a user")
@app_commands.describe(user="Target user", amount="Points amount", reason="Reason")
async def add_points_cmd(interaction: discord.Interaction, user: discord.User, amount: int, reason: str = "Admin adjustment"):
    if not is_admin(interaction.user.id):
        await interaction.response.send_message("Permission denied.", ephemeral=True)
        return
    balance = await add_points(user.id, amount, "admin_add", reason)
    await audit(interaction.user.id, "ADD_POINTS", user.id, f"amount={amount}, reason={reason}")
    await interaction.response.send_message(f"✅ Added {amount} Points to {user.mention}. Balance: {balance}", ephemeral=True)

@bot.tree.command(name="remove_points", description="Admin: remove points from a user")
@app_commands.describe(user="Target user", amount="Points amount", reason="Reason")
async def remove_points_cmd(interaction: discord.Interaction, user: discord.User, amount: int, reason: str = "Admin adjustment"):
    if not is_admin(interaction.user.id):
        await interaction.response.send_message("Permission denied.", ephemeral=True)
        return
    ok, balance = await spend_points(user.id, amount, "admin_remove", reason)
    if not ok:
        await interaction.response.send_message(f"User does not have enough points. Balance: {balance}", ephemeral=True)
        return
    await audit(interaction.user.id, "REMOVE_POINTS", user.id, f"amount={amount}, reason={reason}")
    await interaction.response.send_message(f"✅ Removed {amount} Points from {user.mention}. Balance: {balance}", ephemeral=True)

@bot.tree.command(name="product_create", description="Admin: create shop product")
@app_commands.describe(name="Product name", price="Point price", product_type="ROLE, ITEM, or NFT", role_id="Optional role ID", stock="-1 means unlimited")
async def product_create(interaction: discord.Interaction, name: str, price: int, product_type: str = "ITEM", role_id: Optional[str] = None, stock: int = -1):
    if not is_admin(interaction.user.id):
        await interaction.response.send_message("Permission denied.", ephemeral=True)
        return
    product_type = product_type.upper()
    rid = int(role_id) if role_id and role_id.isdigit() else None
    async with db_pool.acquire() as conn:
        product_id = await conn.fetchval(
            "INSERT INTO products(name, price, product_type, role_id, stock, status) VALUES($1, $2, $3, $4, $5, 'active') RETURNING id",
            name,
            price,
            product_type,
            rid,
            stock,
        )
    await audit(interaction.user.id, "PRODUCT_CREATE", None, f"id={product_id}, name={name}, price={price}")
    await interaction.response.send_message(f"✅ Product created: #{product_id} {name} - {price} Points", ephemeral=True)

@bot.tree.command(name="product_delete", description="Admin: disable shop product")
async def product_delete(interaction: discord.Interaction, product_id: int):
    if not is_admin(interaction.user.id):
        await interaction.response.send_message("Permission denied.", ephemeral=True)
        return
    async with db_pool.acquire() as conn:
        await conn.execute("UPDATE products SET status='inactive' WHERE id=$1", product_id)
    await audit(interaction.user.id, "PRODUCT_DELETE", None, f"id={product_id}")
    await interaction.response.send_message(f"✅ Product #{product_id} disabled.", ephemeral=True)

# =========================
# Events
# =========================
@bot.event
async def on_ready():
    print(f"Community OS Ready: {bot.user}")
    for guild in bot.guilds:
        await refresh_invite_cache(guild)

@bot.event
async def on_message(message: discord.Message):
    await reward_message_if_valid(message)

@bot.event
async def on_member_join(member: discord.Member):
    await track_member_invite(member)

@bot.event
async def on_member_update(before: discord.Member, after: discord.Member):
    await reward_roles(before, after)

# =========================
# Run
# =========================
if not DISCORD_TOKEN:
    raise RuntimeError("DISCORD_TOKEN is missing")
if not GUILD_ID:
    raise RuntimeError("GUILD_ID is missing")

bot.run(DISCORD_TOKEN)
