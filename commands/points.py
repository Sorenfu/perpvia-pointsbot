import discord
from modules import users, points

async def setup(bot):
    @bot.tree.command(name="points", description="View your points balance")
    async def points_cmd(interaction: discord.Interaction):
        user = await users.get_or_create_user(interaction.user)
        balance = await points.get_balance(user["id"])
        await interaction.response.send_message(f"💎 Your balance: **{balance} Points**", ephemeral=True)
