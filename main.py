import os
from datetime import datetime, timezone, timedelta

import discord
from discord import app_commands
from dotenv import load_dotenv
import asyncpg

load_dotenv()

DISCORD_TOKEN = os.getenv('DISCORD_TOKEN')
GUILD_ID = int(os.getenv('GUILD_ID'))
DATABASE_URL = os.getenv('DATABASE_URL')

DB_POOL = None

DAILY_REWARD = 20
DAILY_COOLDOWN = 12


async def init_database():
    global DB_POOL
    DB_POOL = await asyncpg.create_pool(DATABASE_URL)
    print('Database Connected')


async def get_balance(user_id):
    async with DB_POOL.acquire() as conn:
        row = await conn.fetchrow(
            'SELECT points FROM users WHERE discord_id=$1',
            user_id
        )
    return row['points'] if row else 0


async def add_points(user_id, amount, source, reason):
    async with DB_POOL.acquire() as conn:
        await conn.execute(
            '''
            INSERT INTO users(discord_id, points)
            VALUES($1,$2)
            ON CONFLICT(discord_id)
            DO UPDATE SET points = users.points + $2
            ''',
            user_id,
            amount
        )

        await conn.execute(
            '''
            INSERT INTO point_transactions
            (user_id, amount, source, reason)
            VALUES($1,$2,$3,$4)
            ''',
            user_id,
            amount,
            source,
            reason
        )


async def daily_check(user_id):
    async with DB_POOL.acquire() as conn:
        last = await conn.fetchrow(
            '''
            SELECT created_at
            FROM daily_checkins
            WHERE user_id=$1
            ORDER BY created_at DESC
            LIMIT 1
            ''',
            user_id
        )

    now = datetime.now(timezone.utc)

    if last:
        last_time = last['created_at']

        if last_time.tzinfo is None:
            last_time = last_time.replace(tzinfo=timezone.utc)

        if now - last_time < timedelta(hours=DAILY_COOLDOWN):
            return False, '⏳ Daily cooldown active'

    await add_points(
        user_id,
        DAILY_REWARD,
        'daily',
        'Daily Check-in'
    )

    async with DB_POOL.acquire() as conn:
        await conn.execute(
            '''
            INSERT INTO daily_checkins(user_id,reward)
            VALUES($1,$2)
            ''',
            user_id,
            DAILY_REWARD
        )

    balance = await get_balance(user_id)

    return True, f'🎉 Daily +20 Points\n💎 Balance: {balance}'


class CommunityOS(discord.Client):

    def __init__(self):
        intents = discord.Intents.default()
        intents.members = True
        intents.message_content = True
        super().__init__(intents=intents)
        self.tree = app_commands.CommandTree(self)

    async def setup_hook(self):
        print('Community OS Starting')
        await init_database()

        guild = discord.Object(id=GUILD_ID)
        self.tree.clear_commands(guild=guild)
        await self.tree.sync(guild=guild)
        self.tree.copy_global_to(guild=guild)

        synced = await self.tree.sync(guild=guild)
        print('Synced:', [c.name for c in synced])


bot = CommunityOS()


@bot.tree.command(name='balance', description='View points')
async def balance(interaction):
    value = await get_balance(interaction.user.id)
    await interaction.response.send_message(
        f'💎 Balance: {value} Points'
    )


@bot.tree.command(name='daily', description='Daily reward')
async def daily(interaction):
    await interaction.response.defer(ephemeral=True)

    try:
        ok, msg = await daily_check(interaction.user.id)
        await interaction.followup.send(msg, ephemeral=True)

    except Exception as e:
        print('DAILY ERROR:', repr(e))
        await interaction.followup.send(
            'Daily error, check logs',
            ephemeral=True
        )


@bot.tree.command(name='shop', description='Open shop')
async def shop(interaction):
    await interaction.response.send_message(
        '🛒 Shop system ready'
    )


@bot.event
async def on_ready():
    print(f'Community OS Ready: {bot.user}')


bot.run(DISCORD_TOKEN)
