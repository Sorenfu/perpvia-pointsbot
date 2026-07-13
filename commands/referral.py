from __future__ import annotations

import discord
from discord.ext import commands
from modules.users import ensure_user
from modules.referral import store_invite, referral_stats, get_latest_invite_code


async def setup(bot: commands.Bot):
    @bot.tree.command(name="invite", description="Get your personal invite link")
    async def invite(interaction: discord.Interaction):
        if interaction.guild is None or interaction.channel is None:
            await interaction.response.send_message("Use this command inside a server channel.", ephemeral=True)
            return

        await interaction.response.defer(ephemeral=True)
        await ensure_user(bot.db, interaction.user)

        # Reuse the user's existing invite if it's still valid, instead of
        # minting a brand new one on every /invite call (which used to
        # clutter the server with dozens of duplicate links per person).
        invite_obj = None
        existing_code = await get_latest_invite_code(bot.db, interaction.user.id)
        if existing_code:
            try:
                for inv in await interaction.guild.invites():
                    if inv.code == existing_code:
                        invite_obj = inv
                        break
            except discord.Forbidden:
                pass  # Bot lacks Manage Server; fall through and try to create instead.

        if invite_obj is None:
            try:
                invite_obj = await interaction.channel.create_invite(
                    max_age=0,
                    max_uses=0,
                    unique=True,
                    reason=f"Community OS referral invite by {interaction.user.id}",
                )
            except discord.Forbidden:
                await interaction.followup.send("Bot needs Create Invite permission in this channel.", ephemeral=True)
                return
            await store_invite(bot.db, invite_obj.code, interaction.user.id, invite_obj.uses or 0)

        total, rewarded = await referral_stats(bot.db, interaction.user.id)
        await interaction.followup.send(
            f"Your invite link: {invite_obj.url}\nSuccessful rewarded invites: {rewarded}\nTotal tracked invites: {total}",
            ephemeral=True,
        )

    @bot.tree.command(name="referrals", description="Show your referral stats")
    async def referrals(interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        total, rewarded = await referral_stats(bot.db, interaction.user.id)
        await interaction.followup.send(
            f"Referral stats:\nTotal tracked: {total}\nRewarded: {rewarded}\nReward rule: inviter +20, newcomer +10 after first valid message.",
            ephemeral=True,
        )
