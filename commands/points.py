from __future__ import annotations

import discord
from discord.ext import commands
from modules.users import ensure_user
from modules.points import get_balance


async def setup(bot: commands.Bot):
    @bot.tree.command(name="points", description="Show your points balance")
    async def points(interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        await ensure_user(bot.db, interaction.user)
        balance = await get_balance(bot.db, interaction.user.id)
        await interaction.followup.send(f"Your points balance: **{balance}**", ephemeral=True)
