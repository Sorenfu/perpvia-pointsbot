from __future__ import annotations

import asyncio
import logging
import discord
from discord import app_commands
from discord.ext import commands

from config import DISCORD_TOKEN, DATABASE_URL
from database import Database
from modules.users import ensure_user, get_all_user_ids
from modules.referral import (
    refresh_guild_invites,
    handle_member_join,
    process_message_for_referral,
    get_pending_referral_invitee_ids,
)

logging.basicConfig(level=logging.INFO, format="[%(asctime)s] %(levelname)s %(message)s")
log = logging.getLogger("community-os")

COMMAND_MODULES = [
    "commands.user",
    "commands.points",
    "commands.tasks",
    "commands.shop",
    "commands.referral",
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
        # In-memory caches to avoid a DB round trip on every single message.
        # known_user_ids: users we've already upserted, so we don't re-write
        # a row on every message from the same person.
        # pending_referral_ids: invitees still owed their "first message"
        # reward, so we only bother checking referrals for people who are
        # actually eligible instead of querying on every message from anyone.
        self.known_user_ids: set[int] = set()
        self.pending_referral_ids: set[int] = set()

    async def setup_hook(self) -> None:
        for module in COMMAND_MODULES:
            await self.load_extension(module)

        @self.tree.error
        async def on_app_command_error(interaction: discord.Interaction, error: app_commands.AppCommandError):
            log.exception("Slash command error in /%s", getattr(interaction.command, "name", "?"), exc_info=error)
            message = "Something went wrong running that command. Please try again in a moment."
            try:
                if interaction.response.is_done():
                    await interaction.followup.send(message, ephemeral=True)
                else:
                    await interaction.response.send_message(message, ephemeral=True)
            except discord.HTTPException:
                pass

    async def on_ready(self):
        if not self.synced_once:
            try:
                synced = await self.tree.sync()
                log.info("Synced %s slash commands", len(synced))
            except Exception:
                log.exception("Slash command sync failed")
            self.synced_once = True

            try:
                self.known_user_ids = await get_all_user_ids(self.db)
                self.pending_referral_ids = await get_pending_referral_invitee_ids(self.db)
                log.info(
                    "Loaded caches: %s known users, %s pending referrals",
                    len(self.known_user_ids),
                    len(self.pending_referral_ids),
                )
            except Exception:
                log.exception("Failed to warm up in-memory caches")

        for guild in self.guilds:
            await refresh_guild_invites(self, guild)

        log.info("Bot online as %s", self.user)

    async def on_member_join(self, member: discord.Member):
        await ensure_user(self.db, member)
        self.known_user_ids.add(member.id)
        await handle_member_join(self, member)

    async def on_message(self, message: discord.Message):
        if message.author.bot:
            return
        if message.guild is not None:
            author_id = message.author.id
            if author_id not in self.known_user_ids:
                await ensure_user(self.db, message.author)
                self.known_user_ids.add(author_id)
            if author_id in self.pending_referral_ids:
                rewarded = await process_message_for_referral(self.db, author_id)
                if rewarded:
                    self.pending_referral_ids.discard(author_id)
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
