from __future__ import annotations

import asyncio
import logging
import discord
from discord.ext import commands

from config import DISCORD_TOKEN, DATABASE_URL
from database import Database
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

    async def setup_hook(self) -> None:
        for module in COMMAND_MODULES:
            await self.load_extension(module)

    async def on_ready(self):
        if not self.synced_once:
            try:
                synced = await self.tree.sync()
                log.info("Synced %s slash commands", len(synced))
            except Exception:
                log.exception("Slash command sync failed")
            self.synced_once = True

        for guild in self.guilds:
            await refresh_guild_invites(self, guild)

        log.info("Bot online as %s", self.user)

    async def on_member_join(self, member: discord.Member):
        await ensure_user(self.db, member)
        await handle_member_join(self, member)

    async def on_message(self, message: discord.Message):
        if message.author.bot:
            return
        if message.guild is not None:
            await ensure_user(self.db, message.author)
            await process_message_for_referral(self.db, message.author.id)
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
