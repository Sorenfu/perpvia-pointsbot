import os
from datetime import datetime, timezone, timedelta
import discord
from discord import app_commands
from dotenv import load_dotenv
import asyncpg

load_dotenv()

TOKEN=os.getenv('DISCORD_TOKEN')
GUILD_ID=int(os.getenv('GUILD_ID'))
DB=None

DAILY_REWARD=20
DAILY_HOURS=12

SCHEMA='''
CREATE TABLE IF NOT EXISTS users(discord_id BIGINT PRIMARY KEY,points BIGINT DEFAULT 0,created_at TIMESTAMPTZ DEFAULT NOW(),updated_at TIMESTAMPTZ DEFAULT NOW());
CREATE TABLE IF NOT EXISTS point_transactions(id SERIAL PRIMARY KEY,user_id BIGINT,amount INT,source TEXT,reason TEXT,created_at TIMESTAMPTZ DEFAULT NOW());
CREATE TABLE IF NOT EXISTS daily_checkins(id SERIAL PRIMARY KEY,user_id BIGINT,reward INT,created_at TIMESTAMPTZ DEFAULT NOW());
CREATE TABLE IF NOT EXISTS products(id SERIAL PRIMARY KEY,name TEXT,price INT,status BOOLEAN DEFAULT TRUE);
CREATE TABLE IF NOT EXISTS orders(id SERIAL PRIMARY KEY,user_id BIGINT,product_id INT,status TEXT);
'''

async def init_db():
    global DB
    DB=await asyncpg.create_pool(os.getenv('DATABASE_URL'))
    async with DB.acquire() as c:
        await c.execute(SCHEMA)
    print('Database Ready')

async def add_points(uid,amount,source,reason):
    async with DB.acquire() as c:
        await c.execute('INSERT INTO users(discord_id,points) VALUES($1,$2) ON CONFLICT(discord_id) DO UPDATE SET points=users.points+$2,updated_at=NOW()',uid,amount)
        await c.execute('INSERT INTO point_transactions(user_id,amount,source,reason) VALUES($1,$2,$3,$4)',uid,amount,source,reason)

async def balance(uid):
    async with DB.acquire() as c:
        r=await c.fetchrow('SELECT points FROM users WHERE discord_id=$1',uid)
    return r['points'] if r else 0

async def daily(uid):
    async with DB.acquire() as c:
        r=await c.fetchrow('SELECT created_at FROM daily_checkins WHERE user_id=$1 ORDER BY created_at DESC LIMIT 1',uid)
    now=datetime.now(timezone.utc)
    if r:
        last=r['created_at']
        if last.tzinfo is None:
            last=last.replace(tzinfo=timezone.utc)
        if now-last < timedelta(hours=DAILY_HOURS):
            return '⏳ Daily cooldown active'
    await add_points(uid,DAILY_REWARD,'daily','Daily Check-in')
    async with DB.acquire() as c:
        await c.execute('INSERT INTO daily_checkins(user_id,reward) VALUES($1,$2)',uid,DAILY_REWARD)
    return f'🎉 Daily +{DAILY_REWARD} Points\n💎 Balance: {await balance(uid)}'

class Bot(discord.Client):
    def __init__(self):
        intents=discord.Intents.default(); intents.members=True; intents.message_content=True
        super().__init__(intents=intents)
        self.tree=app_commands.CommandTree(self)
    async def setup_hook(self):
        await init_db()
        print('Setup Complete')

bot=Bot()

@bot.tree.command(name='balance',description='balance')
async def balance_cmd(i):
    await i.response.send_message(f'💎 Balance: {await balance(i.user.id)}')

@bot.tree.command(name='daily',description='daily')
async def daily_cmd(i):
    await i.response.defer(ephemeral=True)
    try:
        await i.followup.send(await daily(i.user.id),ephemeral=True)
    except Exception as e:
        print('DAILY ERROR',repr(e))
        await i.followup.send('Daily error',ephemeral=True)

@bot.event
async def on_ready():

    print(f'Community OS Ready: {bot.user}')

    try:
        guild = discord.Object(id=GUILD_ID)

        print('Clearing old guild commands...')
        bot.tree.clear_commands(guild=guild)
        await bot.tree.sync(guild=guild)

        print('Copying global commands...')
        bot.tree.copy_global_to(guild=guild)

        synced = await bot.tree.sync(guild=guild)

        print('COMMAND SYNC SUCCESS:', [x.name for x in synced])

    except Exception as e:
        print('COMMAND SYNC ERROR:', repr(e))

bot.run(TOKEN)
