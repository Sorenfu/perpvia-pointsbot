from __future__ import annotations

import discord
from discord.ext import commands
from modules.users import ensure_user
from modules.points import get_balance
from modules.ui import EMOJI, base_embed


async def setup(bot: commands.Bot):
    @bot.tree.command(name="ping", description="Check bot status")
    async def ping(interaction: discord.Interaction):
        latency_ms = round(bot.latency * 1000)
        embed = base_embed("Pong!", f"Community OS Lite is online.\nLatency: `{latency_ms}ms`")
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @bot.tree.command(name="profile", description="Show your community profile")
    async def profile(interaction: discord.Interaction):
        user = await ensure_user(bot.db, interaction.user)
        balance = await get_balance(bot.db, interaction.user.id)
        embed = base_embed(f"{EMOJI['profile']} Profile")
        embed.set_thumbnail(url=interaction.user.display_avatar.url)
        embed.add_field(name="Username", value=str(user["username"]), inline=True)
        embed.add_field(name="Discord ID", value=str(interaction.user.id), inline=True)
        embed.add_field(name=f"{EMOJI['points']} Points", value=str(balance), inline=True)
        embed.add_field(name="Member Since", value=str(user["created_at"]), inline=False)
        await interaction.response.send_message(embed=embed, ephemeral=True)
