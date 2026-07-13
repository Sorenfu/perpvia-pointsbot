from __future__ import annotations

import discord
from discord import app_commands
from discord.ext import commands
from modules.admin import is_admin, log_admin
from modules.users import ensure_user
from modules.points import add_points
from modules.tasks import create_task
from modules.shop import create_product, list_all_products, set_product_status


def admin_only(interaction: discord.Interaction) -> bool:
    return is_admin(interaction.user.id)


async def setup(bot: commands.Bot):
    @bot.tree.command(name="admin_add_points", description="Admin: add points to a user")
    @app_commands.default_permissions(administrator=True)
    async def admin_add_points(interaction: discord.Interaction, member: discord.Member, amount: int, reason: str = "Admin reward"):
        if not admin_only(interaction):
            await interaction.response.send_message("No permission.", ephemeral=True)
            return
        if amount == 0:
            await interaction.response.send_message("Amount must not be 0.", ephemeral=True)
            return
        await interaction.response.defer(ephemeral=True)
        await ensure_user(bot.db, member)
        await add_points(bot.db, member.id, int(amount), "ADMIN_REWARD", reason)
        await log_admin(bot.db, interaction.user.id, "ADMIN_ADD_POINTS", f"{member.id} {amount} {reason}")
        await interaction.followup.send(f"Added {amount} points to {member.mention}.", ephemeral=True)

    @bot.tree.command(name="admin_add_task", description="Admin: create a task")
    @app_commands.default_permissions(administrator=True)
    async def admin_add_task(interaction: discord.Interaction, name: str, reward: int, description: str = ""):
        if not admin_only(interaction):
            await interaction.response.send_message("No permission.", ephemeral=True)
            return
        if reward < 0:
            await interaction.response.send_message("Reward must be >= 0.", ephemeral=True)
            return
        await interaction.response.defer(ephemeral=True)
        task = await create_task(bot.db, name, reward, description)
        await log_admin(bot.db, interaction.user.id, "ADMIN_ADD_TASK", f"{task['id']} {name} {reward}")
        await interaction.followup.send(f"Created task #{task['id']}: {name}", ephemeral=True)

    @bot.tree.command(name="admin_add_product", description="Admin: create a shop product")
    @app_commands.default_permissions(administrator=True)
    async def admin_add_product(interaction: discord.Interaction, name: str, price: int, role: discord.Role | None = None, description: str = ""):
        if not admin_only(interaction):
            await interaction.response.send_message("No permission.", ephemeral=True)
            return
        if price < 0:
            await interaction.response.send_message("Price must be >= 0 (use 0 for a free product).", ephemeral=True)
            return
        await interaction.response.defer(ephemeral=True)
        product = await create_product(bot.db, name, price, role.id if role else None, description)
        await log_admin(bot.db, interaction.user.id, "ADMIN_ADD_PRODUCT", f"{product['id']} {name} {price}")
        await interaction.followup.send(f"Created product #{product['id']}: {name}", ephemeral=True)

    @bot.tree.command(name="admin_products", description="Admin: list all products, including unlisted ones")
    @app_commands.default_permissions(administrator=True)
    async def admin_products(interaction: discord.Interaction):
        if not admin_only(interaction):
            await interaction.response.send_message("No permission.", ephemeral=True)
            return
        await interaction.response.defer(ephemeral=True)
        products = await list_all_products(bot.db)
        if not products:
            await interaction.followup.send("No products yet.", ephemeral=True)
            return
        lines = [
            f"#{p['id']} **{p['name']}** - {p['price']} points - status: {p['status']}"
            + (f" - role: {p['role_id']}" if p["role_id"] else "")
            for p in products
        ]
        await interaction.followup.send("\n".join(lines), ephemeral=True)

    @bot.tree.command(name="admin_list_product", description="Admin: list (re-activate) a product in the shop")
    @app_commands.default_permissions(administrator=True)
    async def admin_list_product(interaction: discord.Interaction, product_id: int):
        if not admin_only(interaction):
            await interaction.response.send_message("No permission.", ephemeral=True)
            return
        await interaction.response.defer(ephemeral=True)
        product = await set_product_status(bot.db, product_id, "ACTIVE")
        if not product:
            await interaction.followup.send(f"Product #{product_id} not found.", ephemeral=True)
            return
        await log_admin(bot.db, interaction.user.id, "ADMIN_LIST_PRODUCT", f"{product_id}")
        await interaction.followup.send(f"Product #{product_id} ({product['name']}) is now listed in /shop.", ephemeral=True)

    @bot.tree.command(name="admin_unlist_product", description="Admin: unlist (deactivate) a product from the shop")
    @app_commands.default_permissions(administrator=True)
    async def admin_unlist_product(interaction: discord.Interaction, product_id: int):
        if not admin_only(interaction):
            await interaction.response.send_message("No permission.", ephemeral=True)
            return
        await interaction.response.defer(ephemeral=True)
        product = await set_product_status(bot.db, product_id, "INACTIVE")
        if not product:
            await interaction.followup.send(f"Product #{product_id} not found.", ephemeral=True)
            return
        await log_admin(bot.db, interaction.user.id, "ADMIN_UNLIST_PRODUCT", f"{product_id}")
        await interaction.followup.send(f"Product #{product_id} ({product['name']}) has been unlisted from /shop.", ephemeral=True)

    @bot.tree.command(name="admin_stats", description="Admin: show community stats")
    @app_commands.default_permissions(administrator=True)
    async def admin_stats(interaction: discord.Interaction):
        if not admin_only(interaction):
            await interaction.response.send_message("No permission.", ephemeral=True)
            return
        await interaction.response.defer(ephemeral=True)
        users = await bot.db.fetchval("SELECT COUNT(*) FROM users")
        points = await bot.db.fetchval("SELECT COALESCE(SUM(amount), 0) FROM points")
        tasks = await bot.db.fetchval("SELECT COUNT(*) FROM tasks")
        products = await bot.db.fetchval("SELECT COUNT(*) FROM products")
        orders = await bot.db.fetchval("SELECT COUNT(*) FROM orders")
        referrals = await bot.db.fetchval("SELECT COUNT(*) FROM referrals")
        msg = (
            f"Community Stats\n"
            f"Users: {users}\n"
            f"Points total: {points}\n"
            f"Tasks: {tasks}\n"
            f"Products: {products}\n"
            f"Orders: {orders}\n"
            f"Referrals: {referrals}"
        )
        await interaction.followup.send(msg, ephemeral=True)
