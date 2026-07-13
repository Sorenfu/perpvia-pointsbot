from __future__ import annotations

import discord
from discord.ext import commands
from modules.admin import is_admin, log_admin
from modules.users import ensure_user
from modules.points import add_points
from modules.tasks import create_task
from modules.shop import create_product


def admin_only(interaction: discord.Interaction) -> bool:
    return is_admin(interaction.user.id)


async def setup(bot: commands.Bot):
    @bot.tree.command(name="admin_add_points", description="Admin: add points to a user")
    async def admin_add_points(interaction: discord.Interaction, member: discord.Member, amount: int, reason: str = "Admin reward"):
        if not admin_only(interaction):
            await interaction.response.send_message("No permission.", ephemeral=True)
            return
        await ensure_user(bot.db, member)
        await add_points(bot.db, member.id, int(amount), "ADMIN_REWARD", reason)
        await log_admin(bot.db, interaction.user.id, "ADMIN_ADD_POINTS", f"{member.id} {amount} {reason}")
        await interaction.response.send_message(f"Added {amount} points to {member.mention}.", ephemeral=True)

    @bot.tree.command(name="admin_add_task", description="Admin: create a task")
    async def admin_add_task(interaction: discord.Interaction, name: str, reward: int, description: str = ""):
        if not admin_only(interaction):
            await interaction.response.send_message("No permission.", ephemeral=True)
            return
        task = await create_task(bot.db, name, reward, description)
        await log_admin(bot.db, interaction.user.id, "ADMIN_ADD_TASK", f"{task['id']} {name} {reward}")
        await interaction.response.send_message(f"Created task #{task['id']}: {name}", ephemeral=True)

    @bot.tree.command(name="admin_add_product", description="Admin: create a shop product")
    async def admin_add_product(interaction: discord.Interaction, name: str, price: int, role: discord.Role | None = None, description: str = ""):
        if not admin_only(interaction):
            await interaction.response.send_message("No permission.", ephemeral=True)
            return
        product = await create_product(bot.db, name, price, role.id if role else None, description)
        await log_admin(bot.db, interaction.user.id, "ADMIN_ADD_PRODUCT", f"{product['id']} {name} {price}")
        await interaction.response.send_message(f"Created product #{product['id']}: {name}", ephemeral=True)

    @bot.tree.command(name="admin_stats", description="Admin: show community stats")
    async def admin_stats(interaction: discord.Interaction):
        if not admin_only(interaction):
            await interaction.response.send_message("No permission.", ephemeral=True)
            return
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
        await interaction.response.send_message(msg, ephemeral=True)
