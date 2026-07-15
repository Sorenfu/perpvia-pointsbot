from __future__ import annotations

import discord
from discord import app_commands
from discord.ext import commands
from modules.users import ensure_user
from modules.referral import store_invite, referral_stats, INVITER_REWARD, INVITEE_REWARD
from modules.ui import EMOJI, base_embed, error_embed


async def setup(bot: commands.Bot):
    @bot.tree.command(name="invite", description="Create your invite link")
    @app_commands.checks.cooldown(1, 15.0)
    async def invite(interaction: discord.Interaction):
        if interaction.guild is None or interaction.channel is None:
            await interaction.response.send_message(
                embed=error_embed("Server Only", "Use this command inside a server channel."), ephemeral=True
            )
            return

        await ensure_user(bot.db, interaction.user)

        try:
            invite_obj = await interaction.channel.create_invite(
                max_age=0,
                max_uses=0,
                unique=True,
                reason=f"Community OS referral invite by {interaction.user.id}",
            )
        except discord.Forbidden:
            await interaction.response.send_message(
                embed=error_embed("Missing Permission", "Bot needs Create Invite permission in this channel."),
                ephemeral=True,
            )
            return

        await store_invite(bot.db, invite_obj.code, interaction.user.id, invite_obj.uses or 0)
        total, rewarded = await referral_stats(bot.db, interaction.user.id)

        embed = base_embed(f"{EMOJI['invite']} Your Invite Link")
        embed.add_field(name="Link", value=invite_obj.url, inline=False)
        embed.add_field(name="Rewarded Invites", value=str(rewarded), inline=True)
        embed.add_field(name="Total Tracked", value=str(total), inline=True)
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @bot.tree.command(name="referrals", description="Show your referral stats")
    async def referrals(interaction: discord.Interaction):
        total, rewarded = await referral_stats(bot.db, interaction.user.id)
        embed = base_embed(f"{EMOJI['invite']} Referral Stats")
        embed.add_field(name="Total Tracked", value=str(total), inline=True)
        embed.add_field(name="Rewarded", value=str(rewarded), inline=True)
        embed.add_field(
            name="Reward Rule",
            value=f"Inviter +{INVITER_REWARD} {EMOJI['points']} • Newcomer +{INVITEE_REWARD} {EMOJI['points']} after first valid message.",
            inline=False,
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)
