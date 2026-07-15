from __future__ import annotations

import discord
from discord.ext import commands
from modules.users import ensure_user
from modules.points import get_balance, get_history
from modules.ui import EMOJI, base_embed


async def setup(bot: commands.Bot):
    @bot.tree.command(name="points", description="Show your points balance")
    async def points(interaction: discord.Interaction):
        await ensure_user(bot.db, interaction.user)
        balance = await get_balance(bot.db, interaction.user.id)
        embed = base_embed(f"{EMOJI['points']} Points Balance", f"You have **{balance}** points.")
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @bot.tree.command(name="points_history", description="Show your recent points transaction history")
    async def points_history(interaction: discord.Interaction):
        await ensure_user(bot.db, interaction.user)
        rows = await get_history(bot.db, interaction.user.id, 10)

        embed = base_embed(f"{EMOJI['points']} Points History", "Your 10 most recent point transactions.")
        if not rows:
            embed.description = "No point transactions yet."
        else:
            for row in rows:
                amount = int(row["amount"])
                sign = "+" if amount >= 0 else ""
                reason = row["reason"] or row["type"]
                embed.add_field(
                    name=f"{sign}{amount} {EMOJI['points']} · {row['type']}",
                    value=f"{reason}\n{row['created_at']}",
                    inline=False,
                )
        await interaction.response.send_message(embed=embed, ephemeral=True)
