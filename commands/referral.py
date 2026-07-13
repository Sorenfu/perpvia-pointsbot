import discord
from modules import users, referral

async def setup(bot):
    @bot.tree.command(name="invite", description="Create or view your referral invite")
    async def invite_cmd(interaction: discord.Interaction):
        if not interaction.guild or not isinstance(interaction.user, discord.Member):
            await interaction.response.send_message("Use this command inside a server.", ephemeral=True)
            return
        user = await users.get_or_create_user(interaction.user)
        try:
            invite = await interaction.channel.create_invite(max_age=0, max_uses=0, unique=True, reason="Community OS referral")
            await referral.save_invite_link(interaction.guild.id, invite.code, user["id"])
            if hasattr(bot, "invite_cache"):
                bot.invite_cache.setdefault(interaction.guild.id, {})[invite.code] = invite.uses or 0
            total, rewarded, earned = await referral.get_referral_stats(user["id"])
            await interaction.response.send_message(
                f"🎁 **Your Referral Link**\n{invite.url}\n\n"
                f"Invite reward: **+20 Points**\nFriend reward: **+10 Points after first valid message**\n\n"
                f"Total: **{total}** | Rewarded: **{rewarded}** | Earned: **{earned} Points**",
                ephemeral=True,
            )
        except Exception as exc:
            await interaction.response.send_message(
                "I could not create an invite. Please check that the bot has Create Invite permission.\n"
                f"Error: {exc}",
                ephemeral=True,
            )

    @bot.tree.command(name="referrals", description="View your referral stats")
    async def referrals_cmd(interaction: discord.Interaction):
        user = await users.get_or_create_user(interaction.user)
        total, rewarded, earned = await referral.get_referral_stats(user["id"])
        await interaction.response.send_message(
            f"🎁 **Referral Stats**\nTotal invites: **{total}**\nRewarded: **{rewarded}**\nEarned: **{earned} Points**",
            ephemeral=True,
        )
