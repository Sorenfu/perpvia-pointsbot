from __future__ import annotations

import asyncio
import logging
import discord
from discord import app_commands
from discord.ext import commands

from config import DISCORD_TOKEN, DATABASE_URL
from database import Database
from modules.activity import award_message_points
from modules.alerts import send_alert
from modules.ui import error_embed
from modules.users import ensure_user
from modules.referral import refresh_guild_invites, handle_member_join, process_message_for_referral

logging.basicConfig(level=logging.INFO, format="[%(asctime)s] %(levelname)s %(message)s")
log = logging.getLogger("community-os")

COMMAND_MODULES = [
    "commands.user",
    "commands.points",
    "commands.tasks",
    "commands.shop",
    "commands.referral",
    "commands.leaderboard",
    "commands.wallet",
    "commands.admin",
]


class CommunityOSBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.members = True
        intents.message_content = True
        super().__init__(command_prefix="!", intents=intents)
        self.db = Database(DATABASE_URL)
        self.invite_cache: dict[int, dict[str, int]] = {}
        self.synced_once = False
        self.tree.on_error = self.on_app_command_error

    async def setup_hook(self) -> None:
        for module in COMMAND_MODULES:
            await self.load_extension(module)

    async def on_app_command_error(
        self, interaction: discord.Interaction, error: app_commands.AppCommandError
    ) -> None:
        original = getattr(error, "original", error)
        command_name = interaction.command.name if interaction.command else "unknown"

        if isinstance(original, discord.Forbidden):
            message = "Bot is missing permissions to complete this action."
        elif isinstance(error, app_commands.CommandOnCooldown):
            message = f"This command is on cooldown. Try again in {error.retry_after:.1f}s."
        elif isinstance(error, (app_commands.MissingPermissions, app_commands.CheckFailure)):
            message = "You don't have permission to use this command."
        else:
            message = "Something went wrong while running this command. The team has been notified."
            log.exception("Unhandled app command error in /%s", command_name, exc_info=original)
            asyncio.create_task(
                send_alert(self, f"/{command_name} failed", f"{type(original).__name__}: {original}")
            )

        embed = error_embed("Command Error", message)
        try:
            if interaction.response.is_done():
                await interaction.followup.send(embed=embed, ephemeral=True)
            else:
                await interaction.response.send_message(embed=embed, ephemeral=True)
        except discord.HTTPException:
            pass

    async def on_ready(self):
        if not self.synced_once:
            try:
                synced = await self.tree.sync()
                log.info("Synced %s slash commands", len(synced))
            except Exception as exc:
                log.exception("Slash command sync failed")
                await send_alert(self, "Slash command sync failed", f"{type(exc).__name__}: {exc}")
            self.synced_once = True

        for guild in self.guilds:
            await refresh_guild_invites(self, guild)

        log.info("Bot online as %s", self.user)

    async def on_member_join(self, member: discord.Member):
        try:
            await ensure_user(self.db, member)
            await handle_member_join(self, member)
        except Exception as exc:
            log.exception("Error handling member join for %s", member.id)
            await send_alert(self, "on_member_join failed", f"{type(exc).__name__}: {exc}")

    async def on_message(self, message: discord.Message):
        if message.author.bot:
            return
        try:
            if message.guild is not None:
                await ensure_user(self.db, message.author)
                await process_message_for_referral(self.db, message.author.id)
                if not message.content.startswith(self.command_prefix):
                    await award_message_points(self.db, message.author.id)
        except Exception as exc:
            log.exception("Error processing message from %s", message.author.id)
            await send_alert(self, "on_message failed", f"{type(exc).__name__}: {exc}")
        await self.process_commands(message)


async def main():
    log.info("Starting Community OS Lite")
    bot = CommunityOSBot()
    await bot.db.connect()
    log.info("Database connected")
    await bot.db.init_schema()
    log.info("Database initialized")
    try:
        await bot.start(DISCORD_TOKEN)
    finally:
        await bot.db.close()


if __name__ == "__main__":
    asyncio.run(main())
