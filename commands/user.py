from __future__ import annotations

import discord
from discord import app_commands
from discord.ext import commands
from modules.users import ensure_user
from modules.points import get_balance


async def setup(bot: commands.Bot):
    @bot.tree.command(name="ping", description="Check bot status")
    async def ping(interaction: discord.Interaction):
        await interaction.response.send_message("Pong. Community OS Lite is online.", ephemeral=True)

    @bot.tree.command(name="profile", description="Show your community profile")
    async def profile(interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        user = await ensure_user(bot.db, interaction.user)
        balance = await get_balance(bot.db, interaction.user.id)
        embed = discord.Embed(title="Profile", color=0x2B2D31)
        embed.add_field(name="Username", value=str(user["username"]), inline=False)
        embed.add_field(name="Discord ID", value=str(interaction.user.id), inline=False)
        embed.add_field(name="Points", value=str(balance), inline=False)
        embed.add_field(name="Created", value=str(user["created_at"]), inline=False)
        await interaction.followup.send(embed=embed, ephemeral=True)
