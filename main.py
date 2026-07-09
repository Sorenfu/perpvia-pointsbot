import os
from datetime import datetime, timezone, timedelta
import discord
from discord import app_commands
from dotenv import load_dotenv
import asyncpg

load_dotenv()

TOKEN=os.getenv('DISCORD_TOKEN')
GUILD_ID=int(os.getenv('GUILD_ID'))
pool=None

async def init_db():
    global pool
    pool=await asyncpg.create_pool(os.getenv('DATABASE_URL'))
    async with pool.acquire() as c:
        await c.execute('''
        CREATE TABLE IF NOT EXISTS users(discord_id BIGINT PRIMARY KEY,points BIGINT DEFAULT 0);
        CREATE TABLE IF NOT EXISTS point_transactions(id SERIAL PRIMARY KEY,user_id BIGINT,amount INT,source TEXT,reason TEXT);
        CREATE TABLE IF NOT EXISTS daily_checkins(id SERIAL PRIMARY KEY,user_id BIGINT,reward INT,created_at TIMESTAMP DEFAULT NOW());
        CREATE TABLE IF NOT EXISTS products(id SERIAL PRIMARY KEY,name TEXT,price INT,status BOOLEAN DEFAULT TRUE);
        CREATE TABLE IF NOT EXISTS orders(id SERIAL PRIMARY KEY,user_id BIGINT,product_id INT,status TEXT);
        ''')

async def add_points(uid,amount,source,reason):
    async with pool.acquire() as c:
        await c.execute('INSERT INTO users(discord_id,points) VALUES($1,$2) ON CONFLICT(discord_id) DO UPDATE SET points=users.points+$2',uid,amount)
        await c.execute('INSERT INTO point_transactions(user_id,amount,source,reason) VALUES($1,$2,$3,$4)',uid,amount,source,reason)

async def get_points(uid):
    async with pool.acquire() as c:
        r=await c.fetchrow('SELECT points FROM users WHERE discord_id=$1',uid)
    return r['points'] if r else 0

async def do_daily(uid):
    async with pool.acquire() as c:
        last=await c.fetchrow('SELECT created_at FROM daily_checkins WHERE user_id=$1 ORDER BY created_at DESC LIMIT 1',uid)
    if last:
        t=last['created_at']
        if t.tzinfo is None:
            t=t.replace(tzinfo=timezone.utc)
        if datetime.now(timezone.utc)-t < timedelta(hours=12):
            return '⏳ Daily cooldown active'
    await add_points(uid,20,'daily','Daily Check-in')
    async with pool.acquire() as c:
        await c.execute('INSERT INTO daily_checkins(user_id,reward) VALUES($1,$2)',uid,20)
    return f'🎉 Daily +20 Points\nBalance: {await get_points(uid)}'

class Bot(discord.Client):
    def __init__(self):
        intents=discord.Intents.default()
        intents.members=True
        intents.message_content=True
        super().__init__(intents=intents)
        self.tree=app_commands.CommandTree(self)
    async def setup_hook(self):
        print('Starting')
        await init_db()
        print('Database Ready')

bot=Bot()

@bot.tree.command(name='balance')
async def balance(i):
    await i.response.send_message(f'💎 Balance: {await get_points(i.user.id)}')

@bot.tree.command(name='daily')
async def daily(i):
    await i.response.defer(ephemeral=True)
    await i.followup.send(await do_daily(i.user.id),ephemeral=True)

@bot.tree.command(name='shop')
async def shop(i):
    await i.response.send_message('🛒 Shop Ready')

@bot.event
async def on_ready():

    print(
        f"Community OS Ready: {bot.user}"
    )

    try:

        guild = discord.Object(
            id=int(os.getenv("GUILD_ID"))
        )

        # 清理旧命令
        bot.tree.clear_commands(
            guild=guild
        )

        await bot.tree.sync(
            guild=guild
        )


        # 重新同步当前命令
        synced = await bot.tree.sync(
            guild=guild
        )


        print(
            "COMMAND SYNC SUCCESS:",
            [
                cmd.name
                for cmd in synced
            ]
        )


    except Exception as e:

        print(
            "COMMAND SYNC ERROR:",
            repr(e)
        )
    synced=await bot.tree.sync(guild=discord.Object(id=GUILD_ID))
    print('Ready',bot.user,[x.name for x in synced])

bot.run(TOKEN)
