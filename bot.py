import asyncio
import logging
import discord
from discord.ext import commands

from config import DISCORD_TOKEN
from database import db
from modules import users, referral

COMMAND_MODULES = [
    "commands.user",
    "commands.points",
    "commands.tasks",
    "commands.shop",
    "commands.referral",
    "commands.admin",
]

logging.basicConfig(level=logging.INFO, format="[%(asctime)s] %(levelname)s %(message)s")
logger = logging.getLogger("community_os_lite")

class CommunityOSBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.members = True
        intents.message_content = True
        intents.guilds = True
        super().__init__(command_prefix="!", intents=intents)
        self.invite_cache: dict[int, dict[str, int]] = {}

    async def setup_hook(self):
        for module_name in COMMAND_MODULES:
            module = __import__(module_name, fromlist=["setup"])
            await module.setup(self)
            logger.info("Loaded %s", module_name)
        await self.tree.sync()
        logger.info("Slash commands synced")

    async def on_ready(self):
        logger.info("Community OS Lite online as %s", self.user)
        await self.refresh_invite_cache()

    async def refresh_invite_cache(self):
        for guild in self.guilds:
            try:
                invites = await guild.invites()
                self.invite_cache[guild.id] = {invite.code: invite.uses or 0 for invite in invites}
                logger.info("Cached %s invites for guild %s", len(invites), guild.id)
            except Exception as exc:
                logger.warning("Could not cache invites for guild %s: %s", guild.id, exc)

    async def detect_used_invite(self, guild: discord.Guild) -> str | None:
        try:
            before = self.invite_cache.get(guild.id, {})
            invites = await guild.invites()
            used_code = None
            after = {}
            for invite in invites:
                uses = invite.uses or 0
                after[invite.code] = uses
                if uses > before.get(invite.code, 0):
                    used_code = invite.code
            self.invite_cache[guild.id] = after
            return used_code
        except Exception as exc:
            logger.warning("Could not detect used invite: %s", exc)
            return None

bot = CommunityOSBot()

@bot.event
async def on_member_join(member: discord.Member):
    user = await users.get_or_create_user(member)
    invite_code = await bot.detect_used_invite(member.guild)
    if invite_code:
        await referral.create_referral(invite_code, user["id"])
    try:
        await member.send("🎉 Welcome! Use /checkin to earn points, /tasks to view tasks, and /shop to redeem rewards.")
    except Exception:
        pass

@bot.event
async def on_message(message: discord.Message):
    if message.author.bot:
        return
    user = await users.get_or_create_user(message.author)
    ok, msg = await referral.verify_by_message(user["id"], message.content)
    if ok:
        logger.info("Referral rewarded for user %s: %s", message.author.id, msg)
    await bot.process_commands(message)

async def main():
    if not DISCORD_TOKEN:
        raise RuntimeError("DISCORD_TOKEN is not configured")
    logger.info("Starting Community OS Lite")
    await db.connect()
    logger.info("Database connected")
    await db.init_schema()
    logger.info("Database initialized")
    await bot.start(DISCORD_TOKEN)

if __name__ == "__main__":
    asyncio.run(main())
