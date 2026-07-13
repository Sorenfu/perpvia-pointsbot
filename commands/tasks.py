import discord
from discord import app_commands
from modules import users, tasks

async def setup(bot):
    @bot.tree.command(name="tasks", description="View active tasks")
    async def tasks_cmd(interaction: discord.Interaction):
        await users.get_or_create_user(interaction.user)
        rows = await tasks.get_active_tasks()
        if not rows:
            await interaction.response.send_message("📋 No active tasks yet.", ephemeral=True)
            return
        lines = []
        for row in rows:
            lines.append(f"**#{row['id']} {row['name']}** — +{row['reward']} Points\n{row['description'] or ''}")
        await interaction.response.send_message("📋 **Active Tasks**\n\n" + "\n\n".join(lines), ephemeral=True)

    @bot.tree.command(name="checkin", description="Daily check-in for points")
    async def checkin_cmd(interaction: discord.Interaction):
        user = await users.get_or_create_user(interaction.user)
        ok, msg, balance = await tasks.checkin(user["id"])
        if ok:
            await interaction.response.send_message(f"✅ {msg}\nReward: **+10 Points**\nBalance: **{balance}**", ephemeral=True)
        else:
            await interaction.response.send_message(f"⚠️ {msg}\nBalance: **{balance}**", ephemeral=True)

    @bot.tree.command(name="complete_task", description="Complete a task by task ID")
    @app_commands.describe(task_id="Task ID from /tasks")
    async def complete_task_cmd(interaction: discord.Interaction, task_id: int):
        user = await users.get_or_create_user(interaction.user)
        ok, msg, balance = await tasks.complete_task(user["id"], task_id)
        icon = "✅" if ok else "⚠️"
        await interaction.response.send_message(f"{icon} {msg}\nBalance: **{balance}**", ephemeral=True)
