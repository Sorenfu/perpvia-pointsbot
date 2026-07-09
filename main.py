# Replace only the daily part in your current main.py

@bot.tree.command(
    name='daily',
    description='Daily reward'
)
async def daily(interaction: discord.Interaction):

    # Prevent Discord 3 second timeout
    await interaction.response.defer(ephemeral=True)

    print('DAILY START', interaction.user.id)

    try:
        now = datetime.now(timezone.utc)

        async with db_pool.acquire() as conn:
            last = await conn.fetchrow(
                '''
                SELECT created_at
                FROM daily_checkins
                WHERE user_id=$1
                ORDER BY created_at DESC
                LIMIT 1
                ''',
                interaction.user.id
            )

        if last:
            if now - last['created_at'] < timedelta(hours=12):
                await interaction.followup.send(
                    '⏳ Daily cooldown active',
                    ephemeral=True
                )
                return

        # Add points
        await add_points(
            interaction.user.id,
            20,
            'daily',
            'Daily Check-in'
        )

        async with db_pool.acquire() as conn:
            await conn.execute(
                '''
                INSERT INTO daily_checkins(user_id,reward)
                VALUES($1,$2)
                ''',
                interaction.user.id,
                20
            )

        balance = await get_balance(
            interaction.user.id
        )

        await interaction.followup.send(
            f'🎉 Daily +20 Points\n💎 Balance: {balance} Points',
            ephemeral=True
        )

        print('DAILY SUCCESS')

    except Exception as e:
        print('DAILY ERROR:', repr(e))

        await interaction.followup.send(
            'Daily error, check logs.',
            ephemeral=True
        )
