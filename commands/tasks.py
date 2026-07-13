from __future__ import annotations

import discord
from discord.ext import commands
from modules.users import ensure_user
from modules.tasks import list_active_tasks, daily_checkin, complete_task, DAILY_CHECKIN_REWARD


async def setup(bot: commands.Bot):
    @bot.tree.command(name="tasks", description="Show active tasks")
    async def tasks(interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        await ensure_user(bot.db, interaction.user)
        rows = await list_active_tasks(bot.db)
        lines = [f"Daily Check-in - +{DAILY_CHECKIN_REWARD} points. Use /checkin"]
        if rows:
            for row in rows:
                desc = row["description"] or "No description"
                lines.append(f"#{row['id']} {row['name']} - +{row['reward']} points - {desc}")
        await interaction.followup.send("\n".join(lines), ephemeral=True)

    @bot.tree.command(name="checkin", description="Daily check-in for points")
    async def checkin(interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        await ensure_user(bot.db, interaction.user)
        ok = await daily_checkin(bot.db, interaction.user.id)
        if ok:
            await interaction.followup.send(f"Check-in complete. +{DAILY_CHECKIN_REWARD} points.", ephemeral=True)
        else:
            await interaction.followup.send("You already checked in today.", ephemeral=True)

    @bot.tree.command(name="complete_task", description="Complete a task by task ID")
    async def complete_task_command(interaction: discord.Interaction, task_id: int):
        await interaction.response.defer(ephemeral=True)
        await ensure_user(bot.db, interaction.user)
        task, status = await complete_task(bot.db, interaction.user.id, task_id)
        if status == "TASK_NOT_FOUND":
            await interaction.followup.send("Task not found or inactive.", ephemeral=True)
        elif status == "ALREADY_DONE":
            await interaction.followup.send("You already completed this task.", ephemeral=True)
        else:
            await interaction.followup.send(f"Task completed: {task['name']}. +{task['reward']} points.", ephemeral=True)
