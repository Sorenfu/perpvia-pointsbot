# Replace current /daily handler

@bot.tree.command(name='daily', description='Daily reward')
async def daily(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)
    print('DAILY START')
    try:
        result = await daily_checkin(interaction.user.id)
        print('DAILY RESULT:', result)
        if isinstance(result, tuple):
            await interaction.followup.send(result[1], ephemeral=True)
        else:
            await interaction.followup.send(result, ephemeral=True)
    except Exception as e:
        print('DAILY ERROR:', repr(e))
        await interaction.followup.send('Daily system error, check logs.', ephemeral=True)
