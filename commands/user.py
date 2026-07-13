import discord
from discord import app_commands
from modules import users, points

async def setup(bot):
    @bot.tree.command(name="profile", description="View your Community OS profile")
    async def profile(interaction: discord.Interaction):
        user = await users.get_or_create_user(interaction.user)
        balance = await points.get_balance(user["id"])
        embed = discord.Embed(title="👤 Profile", color=0x2B6EF2)
        embed.add_field(name="Username", value=user["username"] or interaction.user.name, inline=False)
        embed.add_field(name="Discord ID", value=str(interaction.user.id), inline=False)
        embed.add_field(name="Points", value=str(balance), inline=False)
        embed.add_field(name="Created", value=str(user["created_at"]), inline=False)
        await interaction.response.send_message(embed=embed, ephemeral=True)
