import discord
from discord import app_commands
from modules import users, points, tasks, shop, admin
from database import db

async def require_admin(interaction: discord.Interaction) -> bool:
    if not await admin.is_admin(interaction.user.id):
        await interaction.response.send_message("❌ You are not allowed to use this command.", ephemeral=True)
        return False
    return True

async def setup(bot):
    @bot.tree.command(name="admin_add_points", description="Admin: add points to a user")
    @app_commands.describe(member="Target member", amount="Points amount", reason="Reason")
    async def admin_add_points(interaction: discord.Interaction, member: discord.Member, amount: int, reason: str = "Admin reward"):
        if not await require_admin(interaction):
            return
        target = await users.get_or_create_user(member)
        balance = await points.add_points(target["id"], amount, "ADMIN_REWARD", reason)
        await admin.log_admin(interaction.user.id, "ADD_POINTS", f"target={member.id} amount={amount}")
        await interaction.response.send_message(f"✅ Added {amount} points to {member.mention}. New balance: {balance}", ephemeral=True)

    @bot.tree.command(name="admin_add_task", description="Admin: create a manual task")
    @app_commands.describe(name="Task name", reward="Reward points", description="Task description")
    async def admin_add_task(interaction: discord.Interaction, name: str, reward: int, description: str = ""):
        if not await require_admin(interaction):
            return
        task = await tasks.create_task(name, reward, description, "MANUAL")
        await admin.log_admin(interaction.user.id, "CREATE_TASK", f"task={task['id']} reward={reward}")
        await interaction.response.send_message(f"✅ Created task #{task['id']}: {name} (+{reward} Points)", ephemeral=True)

    @bot.tree.command(name="admin_add_product", description="Admin: create a shop product")
    @app_commands.describe(name="Product name", price="Point price", role_id="Discord Role ID", description="Product description")
    async def admin_add_product(interaction: discord.Interaction, name: str, price: int, role_id: str = "", description: str = ""):
        if not await require_admin(interaction):
            return
        rid = int(role_id) if role_id.strip() else None
        product = await shop.create_product(name, price, rid, description)
        await admin.log_admin(interaction.user.id, "CREATE_PRODUCT", f"product={product['id']} price={price} role_id={rid}")
        await interaction.response.send_message(f"✅ Created product #{product['id']}: {name} ({price} Points)", ephemeral=True)

    @bot.tree.command(name="admin_stats", description="Admin: view community stats")
    async def admin_stats(interaction: discord.Interaction):
        if not await require_admin(interaction):
            return
        user_count = await db.fetchval("SELECT COUNT(*) FROM users")
        points_issued = await db.fetchval("SELECT COALESCE(SUM(amount),0) FROM points WHERE amount > 0")
        points_spent = await db.fetchval("SELECT ABS(COALESCE(SUM(amount),0)) FROM points WHERE amount < 0")
        task_count = await db.fetchval("SELECT COUNT(*) FROM tasks")
        product_count = await db.fetchval("SELECT COUNT(*) FROM products")
        order_count = await db.fetchval("SELECT COUNT(*) FROM orders")
        referral_count = await db.fetchval("SELECT COUNT(*) FROM referrals WHERE rewarded=true")
        await interaction.response.send_message(
            "📊 **Community Stats**\n"
            f"Users: **{user_count}**\n"
            f"Points issued: **{points_issued}**\n"
            f"Points spent: **{points_spent}**\n"
            f"Tasks: **{task_count}**\n"
            f"Products: **{product_count}**\n"
            f"Orders: **{order_count}**\n"
            f"Rewarded referrals: **{referral_count}**",
            ephemeral=True,
        )
