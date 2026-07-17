from __future__ import annotations

import discord
from discord import app_commands
from discord.ext import commands

from config import OWNER_ID
from modules.users import ensure_user
from modules.points import get_balance
from modules.shop import list_products, get_product, get_redeemed_product_ids, redeem_product
from modules.wallet import get_wallet, submit_unverified_wallet
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


def wallet_status_text(wallet_row) -> str:
    if not wallet_row:
        return "Not on file"
    tag = "✅ Verified" if wallet_row["verified"] else "⚠️ Self-reported (not signature-verified)"
    return f"`{wallet_row['wallet_address']}` — {tag}"


async def notify_admin_redemption(bot: commands.Bot, member: discord.Member, product, wallet_row) -> None:
    wallet_line = wallet_status_text(wallet_row) if product["requires_wallet"] else "Not required"
    embed = base_embed(
        f"{EMOJI['shop']} New Redemption",
        (
            f"**{product['name']}** (#{product['id']})\n"
            f"Redeemed by: {member.mention} ({member})\n"
            f"Price: {product['price']} {EMOJI['points']}\n"
            f"Wallet: {wallet_line}"
        ),
    )
    try:
        owner = await bot.fetch_user(OWNER_ID)
        await owner.send(embed=embed)
    except discord.HTTPException:
        pass


class WalletAddressModal(discord.ui.Modal, title="Submit Your EVM Wallet"):
    def __init__(self, bot: commands.Bot, member: discord.Member, product):
        super().__init__()
        self.bot = bot
        self.member = member
        self.product = product
        self.address_input = discord.ui.TextInput(
            label="EVM wallet address",
            placeholder="0x1234...abcd",
            required=True,
            max_length=100,
        )
        self.add_item(self.address_input)

    async def on_submit(self, interaction: discord.Interaction) -> None:
        ok, result = await submit_unverified_wallet(self.bot.db, self.member.id, self.address_input.value)
        if not ok:
            await interaction.response.send_message(
                embed=error_embed("Invalid Wallet", f"{result} Run `/redeem product_id:{self.product['id']}` again to retry."),
                ephemeral=True,
            )
            return

        wallet_row = await get_wallet(self.bot.db, self.member.id)
        redeem_ok, msg = await redeem_product(
            self.bot.db,
            self.member,
            self.product["id"],
            wallet_row["wallet_address"] if wallet_row else None,
            wallet_row["verified"] if wallet_row else None,
        )
        embed = success_embed("Redeemed", msg) if redeem_ok else error_embed("Redeem Failed", msg)
        await interaction.response.edit_message(embed=embed, view=None)

        if redeem_ok:
            await notify_admin_redemption(self.bot, self.member, self.product, wallet_row)


class RedeemConfirmView(discord.ui.View):
    def __init__(self, bot: commands.Bot, member: discord.Member, product, wallet_row):
        super().__init__(timeout=60)
        self.bot = bot
        self.member = member
        self.product = product
        self.wallet_row = wallet_row

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
        if self.product["requires_wallet"] and not self.wallet_row:
            await interaction.response.send_modal(WalletAddressModal(self.bot, self.member, self.product))
            return

        self.stop()
        ok, msg = await redeem_product(
            self.bot.db,
            self.member,
            self.product["id"],
            self.wallet_row["wallet_address"] if self.wallet_row else None,
            self.wallet_row["verified"] if self.wallet_row else None,
        )
        embed = success_embed("Redeemed", msg) if ok else error_embed("Redeem Failed", msg)
        for child in self.children:
            child.disabled = True
        await interaction.response.edit_message(embed=embed, view=self)

        if ok:
            await notify_admin_redemption(self.bot, self.member, self.product, self.wallet_row)

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
                wallet_tag = " • 🔑 Requires wallet" if p["requires_wallet"] else ""
                embed.add_field(
                    name=f"#{p['id']} · {p['name']} — {p['price']} {EMOJI['points']}",
                    value=f"{desc}\n{role_text} • Stock: {product_stock_text(p['stock'])}{owned_text}{wallet_tag}",
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

        wallet_row = None
        wallet_line = ""
        if product["requires_wallet"]:
            wallet_row = await get_wallet(bot.db, interaction.user.id)
            if wallet_row:
                wallet_line = f"\n{EMOJI['profile']} Wallet on file: {wallet_status_text(wallet_row)}"
            else:
                wallet_line = (
                    f"\n{EMOJI['profile']} This item requires an EVM wallet address — "
                    "you'll be asked to submit one after confirming."
                )

        embed = base_embed(
            f"{EMOJI['shop']} Confirm Redemption",
            (
                f"**{product['name']}** — {price} {EMOJI['points']}\n"
                f"{role_text} • Stock: {product_stock_text(product['stock'])}{wallet_line}\n\n"
                f"Your balance: **{balance}** {EMOJI['points']}\n"
                f"After redemption: **{balance - price}** {EMOJI['points']}\n\n"
                "Confirm this redemption? This action cannot be undone."
            ),
        )
        view = RedeemConfirmView(bot, interaction.user, product, wallet_row)
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
