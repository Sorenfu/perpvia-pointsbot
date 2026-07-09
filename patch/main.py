# Replace setup_hook in main.py

async def setup_hook(self):
    print('Community OS Starting')

    await init_database()
    await init_redis()

    try:
        guild = discord.Object(id=GUILD_ID)

        print('Clearing old guild commands')
        self.tree.clear_commands(guild=guild)
        await self.tree.sync(guild=guild)

        self.tree.copy_global_to(guild=guild)

        synced = await self.tree.sync(guild=guild)

        print('Synced Commands:', [x.name for x in synced])

    except Exception as e:
        print('Command Sync Error:', repr(e))
        raise


@bot.event
async def on_ready():
    print(f'Community OS Ready: {bot.user}')
