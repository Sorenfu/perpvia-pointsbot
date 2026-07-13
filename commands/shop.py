from __future__ import annotations

import discord
from discord.ext import commands
from modules.users import ensure_user
from modules.shop import list_products, redeem_product


async def setup(bot: commands.Bot):
    @bot.tree.command(name="shop", description="Show active shop products")
    async def shop(interaction: discord.Interaction):
        await ensure_user(bot.db, interaction.user)
        products = await list_products(bot.db)
        if not products:
            await interaction.response.send_message("No active products yet.", ephemeral=True)
            return
        lines = []
        for p in products:
            desc = p["description"] or "No description"
            role_text = f"Role ID: {p['role_id']}" if p["role_id"] else "No role"
            lines.append(f"#{p['id']} **{p['name']}** - {p['price']} points - {role_text}\n{desc}")
        lines.append("\nUse /redeem product_id:<id> to redeem.")
        await interaction.response.send_message("\n\n".join(lines), ephemeral=True)

    @bot.tree.command(name="redeem", description="Redeem a shop product by product ID")
    async def redeem(interaction: discord.Interaction, product_id: int):
        if not isinstance(interaction.user, discord.Member):
            await interaction.response.send_message("This command must be used inside a server.", ephemeral=True)
            return
        await ensure_user(bot.db, interaction.user)
        ok, msg = await redeem_product(bot.db, interaction.user, product_id)
        await interaction.response.send_message(msg, ephemeral=True)

    @bot.tree.command(name="orders", description="Show your recent shop orders")
    async def orders(interaction: discord.Interaction):
        rows = await bot.db.fetch(
            '''
            SELECT o.id, o.price, o.status, o.created_at, p.name
            FROM orders o
            LEFT JOIN products p ON p.id=o.product_id
            WHERE o.discord_id=$1
            ORDER BY o.id DESC
            LIMIT 10
            ''',
            int(interaction.user.id),
        )
        if not rows:
            await interaction.response.send_message("No orders yet.", ephemeral=True)
            return
        lines = [f"#{r['id']} {r['name']} - {r['price']} points - {r['status']} - {r['created_at']}" for r in rows]
        await interaction.response.send_message("\n".join(lines), ephemeral=True)
