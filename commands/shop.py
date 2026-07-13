import discord
from discord import app_commands
from modules import users, shop

async def setup(bot):
    @bot.tree.command(name="shop", description="View active shop products")
    async def shop_cmd(interaction: discord.Interaction):
        await users.get_or_create_user(interaction.user)
        rows = await shop.get_products()
        if not rows:
            await interaction.response.send_message("🛒 No active products yet.", ephemeral=True)
            return
        lines = []
        for row in rows:
            reward = f"Role ID: {row['role_id']}" if row['role_id'] else "No role configured"
            lines.append(f"**#{row['id']} {row['name']}** — {row['price']} Points\n{row['description'] or ''}\n{reward}")
        await interaction.response.send_message("🛒 **Community Shop**\nUse `/redeem product_id:<id>` to redeem.\n\n" + "\n\n".join(lines), ephemeral=True)

    @bot.tree.command(name="redeem", description="Redeem a shop product by ID")
    @app_commands.describe(product_id="Product ID from /shop")
    async def redeem_cmd(interaction: discord.Interaction, product_id: int):
        if not isinstance(interaction.user, discord.Member):
            await interaction.response.send_message("This command must be used inside a server.", ephemeral=True)
            return
        user = await users.get_or_create_user(interaction.user)
        ok, msg, balance = await shop.redeem_product(interaction.user, user["id"], product_id)
        icon = "✅" if ok else "❌"
        await interaction.response.send_message(f"{icon} {msg}\nBalance: **{balance}**", ephemeral=True)

    @bot.tree.command(name="orders", description="View your recent orders")
    async def orders_cmd(interaction: discord.Interaction):
        user = await users.get_or_create_user(interaction.user)
        rows = await shop.get_orders(user["id"])
        if not rows:
            await interaction.response.send_message("📦 No orders yet.", ephemeral=True)
            return
        lines = [f"#{r['id']} {r['product_name']} — {r['price']} Points — {r['status']}" for r in rows]
        await interaction.response.send_message("📦 **Recent Orders**\n" + "\n".join(lines), ephemeral=True)
