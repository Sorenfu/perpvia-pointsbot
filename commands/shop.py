from __future__ import annotations

import discord
from discord import app_commands
from discord.ext import commands
from modules.users import ensure_user
from modules.points import get_balance
from modules.shop import list_products, get_product, get_redeemed_product_ids, redeem_product
from modules.ui import EMOJI, base_embed, error_embed, success_embed, warning_embed, paginate_footer, send_paginated

PRODUCTS_PER_PAGE = 6
ORDERS_PER_PAGE = 8
ORDERS_MAX_ROWS = 50


def product_stock_text(stock: int | None) -> str:
    if stock is None:
        return "Unlimited"
    if stock <= 0:
        return f"{EMOJI['sold_out']} Sold out"
    return f"{stock} left"


class RedeemConfirmView(discord.ui.View):
    def __init__(self, bot: commands.Bot, member: discord.Member, product):
        super().__init__(timeout=60)
        self.bot = bot
        self.member = member
        self.product = product

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.member.id:
            await interaction.response.send_message(
                embed=error_embed("Not Yours", "This confirmation isn't for you."), ephemeral=True
            )
            return False
        return True

    async def on_timeout(self) -> None:
        for child in self.children:
            child.disabled = True

    @discord.ui.button(label="Confirm", style=discord.ButtonStyle.success, emoji="✅")
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.stop()
        ok, msg = await redeem_product(self.bot.db, self.member, self.product["id"])
        embed = success_embed("Redeemed", msg) if ok else error_embed("Redeem Failed", msg)
        for child in self.children:
            child.disabled = True
        await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.secondary, emoji="✖️")
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.stop()
        for child in self.children:
            child.disabled = True
        await interaction.response.edit_message(
            embed=warning_embed("Cancelled", "Redemption cancelled. No points were spent."), view=self
        )


async def setup(bot: commands.Bot):
    @bot.tree.command(name="shop", description="Show active shop products")
    async def shop(interaction: discord.Interaction):
        await ensure_user(bot.db, interaction.user)
        products = await list_products(bot.db)
        if not products:
            await interaction.response.send_message(
                embed=base_embed(f"{EMOJI['shop']} Shop", "No active products yet."), ephemeral=True
            )
            return

        redeemed_ids = await get_redeemed_product_ids(bot.db, interaction.user.id)

        chunks = [products[i : i + PRODUCTS_PER_PAGE] for i in range(0, len(products), PRODUCTS_PER_PAGE)]
        pages = []
        for page_num, chunk in enumerate(chunks, start=1):
            embed = base_embed(f"{EMOJI['shop']} Shop", "Use `/redeem product_id:<id>` to redeem an item.")
            for p in chunk:
                desc = p["description"] or "No description"
                role_text = f"Role: <@&{p['role_id']}>" if p["role_id"] else "No role"
                owned_text = " • Already redeemed" if p["id"] in redeemed_ids else ""
                embed.add_field(
                    name=f"#{p['id']} · {p['name']} — {p['price']} {EMOJI['points']}",
                    value=f"{desc}\n{role_text} • Stock: {product_stock_text(p['stock'])}{owned_text}",
                    inline=False,
                )
            paginate_footer(embed, page_num, len(chunks))
            pages.append(embed)

        await send_paginated(interaction, pages)

    @bot.tree.command(name="redeem", description="Redeem a shop product by product ID")
    @app_commands.checks.cooldown(1, 5.0)
    async def redeem(interaction: discord.Interaction, product_id: int):
        if not isinstance(interaction.user, discord.Member):
            await interaction.response.send_message(
                embed=error_embed("Server Only", "This command must be used inside a server."), ephemeral=True
            )
            return
        await ensure_user(bot.db, interaction.user)

        product = await get_product(bot.db, product_id)
        if not product:
            await interaction.response.send_message(
                embed=error_embed("Product Not Found", f"No active product with ID #{product_id}."), ephemeral=True
            )
            return

        balance = await get_balance(bot.db, interaction.user.id)
        price = int(product["price"])
        role_text = f"Role: <@&{product['role_id']}>" if product["role_id"] else "No role"

        embed = base_embed(
            f"{EMOJI['shop']} Confirm Redemption",
            (
                f"**{product['name']}** — {price} {EMOJI['points']}\n"
                f"{role_text} • Stock: {product_stock_text(product['stock'])}\n\n"
                f"Your balance: **{balance}** {EMOJI['points']}\n"
                f"After redemption: **{balance - price}** {EMOJI['points']}\n\n"
                "Confirm this redemption? This action cannot be undone."
            ),
        )
        view = RedeemConfirmView(bot, interaction.user, product)
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

    @bot.tree.command(name="orders", description="Show your recent shop orders")
    async def orders(interaction: discord.Interaction):
        rows = await bot.db.fetch(
            '''
            SELECT o.id, o.price, o.status, o.created_at, p.name
            FROM orders o
            LEFT JOIN products p ON p.id=o.product_id
            WHERE o.discord_id=$1
            ORDER BY o.id DESC
            LIMIT $2
            ''',
            int(interaction.user.id),
            ORDERS_MAX_ROWS,
        )
        if not rows:
            await interaction.response.send_message(
                embed=base_embed(f"{EMOJI['reward']} Your Orders", "No orders yet."), ephemeral=True
            )
            return

        chunks = [rows[i : i + ORDERS_PER_PAGE] for i in range(0, len(rows), ORDERS_PER_PAGE)]
        pages = []
        for page_num, chunk in enumerate(chunks, start=1):
            embed = base_embed(f"{EMOJI['reward']} Your Orders")
            for r in chunk:
                embed.add_field(
                    name=f"#{r['id']} · {r['name']}",
                    value=f"{r['price']} {EMOJI['points']} points • {r['status']} • {r['created_at']}",
                    inline=False,
                )
            paginate_footer(embed, page_num, len(chunks))
            pages.append(embed)

        await send_paginated(interaction, pages)
