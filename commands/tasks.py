from __future__ import annotations

import discord
from discord import app_commands
from discord.ext import commands

from config import TASK_REVIEW_CHANNEL_ID
from modules.admin import is_admin, log_admin
from modules.users import ensure_user
from modules.tasks import (
    list_active_tasks,
    daily_checkin,
    complete_task,
    create_submission,
    approve_submission,
    reject_submission,
    get_submission_with_task,
    set_submission_message,
    is_review_enabled,
    DAILY_CHECKIN_REWARD,
    CATEGORY_BASIC,
    CATEGORY_ADVANCED,
    category_label,
    task_window_text,
    reward_text,
)
from modules.activity import (
    get_today_progress,
    MESSAGE_POINT_REWARD,
    MESSAGE_POINT_COOLDOWN_SECONDS,
    MESSAGE_POINT_DAILY_CAP,
)
from modules.ui import (
    EMOJI,
    base_embed,
    error_embed,
    success_embed,
    warning_embed,
    paginate_footer,
    send_paginated,
    COLOR_SUCCESS,
    COLOR_ERROR,
    COLOR_WARNING,
)

TASKS_PER_PAGE = 5


def task_field(row) -> tuple[str, str]:
    desc = row["description"] or "No description"
    window = task_window_text(row)
    if row["category"] == CATEGORY_BASIC:
        how_to = f"Use `/complete_task task_id:{row['id']}`"
    elif is_review_enabled():
        how_to = f"Use `/submit_task task_id:{row['id']}` with a link/description and/or a screenshot for admin review"
    else:
        how_to = "Complete it, then contact an admin for review — not self-claimable."
    name = f"#{row['id']} · {row['name']} · {category_label(row['category'])}"
    value = f"{reward_text(row['reward'], row['reward_max'])} {EMOJI['points']} points\n{desc}\n{window}\n{how_to}"
    return name, value


def build_review_embed(submission, task_name: str, task_reward: int, task_reward_max: int | None = None) -> discord.Embed:
    embed = base_embed(f"⭐ Task Submission #{submission['id']}", color=COLOR_WARNING)
    embed.add_field(name="Task", value=f"#{submission['task_id']} · {task_name}", inline=True)
    embed.add_field(name=f"{EMOJI['points']} Reward", value=reward_text(task_reward, task_reward_max), inline=True)
    embed.add_field(name="Submitted By", value=f"<@{submission['discord_id']}>", inline=True)
    proof_text = submission["proof"] or ("Screenshot attached below." if submission["proof_image_url"] else "No proof provided.")
    embed.add_field(name="Proof", value=proof_text, inline=False)
    embed.add_field(name="Submitted At", value=str(submission["created_at"]), inline=False)
    if submission["proof_image_url"]:
        embed.set_image(url=submission["proof_image_url"])
    return embed


async def notify_member(bot: commands.Bot, discord_id: int, embed: discord.Embed) -> None:
    try:
        user = await bot.fetch_user(int(discord_id))
        await user.send(embed=embed)
    except discord.HTTPException:
        pass


class ApprovalAmountModal(discord.ui.Modal, title="Approve & Score Submission"):
    def __init__(self, submission_id: int, default_amount: int, max_amount: int | None = None):
        super().__init__()
        self.submission_id = submission_id
        if max_amount is not None and max_amount > default_amount:
            placeholder = f"Suggested range: {default_amount}-{max_amount} — pick a value based on quality"
        else:
            placeholder = f"Base reward is {default_amount} — raise it for a strong submission"
        self.amount_input = discord.ui.TextInput(
            label="Points to award",
            default=str(default_amount),
            placeholder=placeholder,
            required=True,
            max_length=10,
        )
        self.add_item(self.amount_input)

    async def on_submit(self, interaction: discord.Interaction) -> None:
        raw = self.amount_input.value.strip()
        try:
            amount = int(raw)
        except ValueError:
            await interaction.response.send_message(
                embed=error_embed("Invalid Amount", f"'{raw}' is not a whole number."), ephemeral=True
            )
            return
        if amount < 0:
            await interaction.response.send_message(
                embed=error_embed("Invalid Amount", "Points must be zero or positive."), ephemeral=True
            )
            return

        bot = interaction.client
        result, status = await approve_submission(bot.db, self.submission_id, interaction.user.id, amount)
        if status != "OK" or result is None:
            await interaction.response.send_message(
                embed=error_embed("Already Handled", "This submission was already reviewed or no longer exists."),
                ephemeral=True,
            )
            return

        embed = build_review_embed(result, result["task_name"], result["task_reward"], result["task_reward_max"])
        embed.color = COLOR_SUCCESS
        embed.add_field(
            name="Result", value=f"✅ Approved by <@{interaction.user.id}> — awarded **{amount}** {EMOJI['points']}", inline=False
        )
        await interaction.response.edit_message(embed=embed, view=None)
        await log_admin(bot.db, interaction.user.id, "TASK_SUBMISSION_APPROVED", f"{self.submission_id} amount={amount}")

        await notify_member(
            bot,
            result["discord_id"],
            success_embed(
                "Task Approved",
                f"Your submission for **{result['task_name']}** was approved. +{amount} {EMOJI['points']} points!",
            ),
        )


class ApproveSubmissionButton(
    discord.ui.DynamicItem[discord.ui.Button], template=r"task_review:approve:(?P<submission_id>\d+)"
):
    def __init__(self, submission_id: int):
        super().__init__(
            discord.ui.Button(
                style=discord.ButtonStyle.success,
                label="Approve",
                emoji="✅",
                custom_id=f"task_review:approve:{submission_id}",
            )
        )
        self.submission_id = submission_id

    @classmethod
    async def from_custom_id(cls, interaction: discord.Interaction, item: discord.ui.Item, match, /):
        return cls(int(match["submission_id"]))

    async def callback(self, interaction: discord.Interaction) -> None:
        if not is_admin(interaction.user):
            await interaction.response.send_message(
                embed=error_embed("No Permission", "You are not authorized to review submissions."), ephemeral=True
            )
            return

        bot = interaction.client
        submission = await get_submission_with_task(bot.db, self.submission_id)
        if submission is None or submission["status"] != "PENDING":
            await interaction.response.send_message(
                embed=error_embed("Already Handled", "This submission was already reviewed or no longer exists."),
                ephemeral=True,
            )
            return

        await interaction.response.send_modal(
            ApprovalAmountModal(self.submission_id, submission["task_reward"], submission["task_reward_max"])
        )


class RejectSubmissionButton(
    discord.ui.DynamicItem[discord.ui.Button], template=r"task_review:reject:(?P<submission_id>\d+)"
):
    def __init__(self, submission_id: int):
        super().__init__(
            discord.ui.Button(
                style=discord.ButtonStyle.danger,
                label="Reject",
                emoji="❌",
                custom_id=f"task_review:reject:{submission_id}",
            )
        )
        self.submission_id = submission_id

    @classmethod
    async def from_custom_id(cls, interaction: discord.Interaction, item: discord.ui.Item, match, /):
        return cls(int(match["submission_id"]))

    async def callback(self, interaction: discord.Interaction) -> None:
        if not is_admin(interaction.user):
            await interaction.response.send_message(
                embed=error_embed("No Permission", "You are not authorized to review submissions."), ephemeral=True
            )
            return

        bot = interaction.client
        result, status = await reject_submission(bot.db, self.submission_id, interaction.user.id)
        if status != "OK" or result is None:
            await interaction.response.send_message(
                embed=error_embed("Already Handled", "This submission was already reviewed or no longer exists."),
                ephemeral=True,
            )
            return

        embed = build_review_embed(result, result["task_name"], result["task_reward"], result["task_reward_max"])
        embed.color = COLOR_ERROR
        embed.add_field(name="Result", value=f"❌ Rejected by <@{interaction.user.id}>", inline=False)
        await interaction.response.edit_message(embed=embed, view=None)
        await log_admin(bot.db, interaction.user.id, "TASK_SUBMISSION_REJECTED", str(self.submission_id))

        await notify_member(
            bot,
            result["discord_id"],
            error_embed(
                "Task Rejected",
                f"Your submission for **{result['task_name']}** was rejected. Feel free to fix it up and resubmit.",
            ),
        )


async def setup(bot: commands.Bot):
    if is_review_enabled():
        bot.add_dynamic_items(ApproveSubmissionButton, RejectSubmissionButton)

    @bot.tree.command(name="tasks", description="Show active tasks")
    async def tasks(interaction: discord.Interaction):
        await ensure_user(bot.db, interaction.user)
        rows = await list_active_tasks(bot.db)

        chat_progress = await get_today_progress(bot.db, interaction.user.id)

        def build_base_embed() -> discord.Embed:
            embed = base_embed(f"{EMOJI['task']} Community Tasks")
            embed.add_field(
                name=f"{EMOJI['checkin']} Daily Check-in",
                value=f"+{DAILY_CHECKIN_REWARD} {EMOJI['points']} points • Use `/checkin`",
                inline=False,
            )
            embed.add_field(
                name="💬 Daily Chat Activity",
                value=(
                    f"+{MESSAGE_POINT_REWARD} {EMOJI['points']} per message "
                    f"(once every {MESSAGE_POINT_COOLDOWN_SECONDS}s)\n"
                    f"Today's progress: **{chat_progress}/{MESSAGE_POINT_DAILY_CAP}** points"
                ),
                inline=False,
            )
            return embed

        basic_rows = [r for r in rows if r["category"] == CATEGORY_BASIC]
        advanced_rows = [r for r in rows if r["category"] == CATEGORY_ADVANCED]
        ordered_rows = basic_rows + advanced_rows

        if not ordered_rows:
            embed = build_base_embed()
            embed.add_field(name="No extra tasks yet", value="Check back later.", inline=False)
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        chunks = [ordered_rows[i : i + TASKS_PER_PAGE] for i in range(0, len(ordered_rows), TASKS_PER_PAGE)]
        pages = []
        for page_num, chunk in enumerate(chunks, start=1):
            embed = build_base_embed()
            for row in chunk:
                name, value = task_field(row)
                embed.add_field(name=name, value=value, inline=False)
            paginate_footer(embed, page_num, len(chunks))
            pages.append(embed)

        await send_paginated(interaction, pages)

    @bot.tree.command(name="checkin", description="Daily check-in for points")
    async def checkin(interaction: discord.Interaction):
        await ensure_user(bot.db, interaction.user)
        ok = await daily_checkin(bot.db, interaction.user.id)
        if ok:
            await interaction.response.send_message(
                embed=success_embed("Checked In", f"{EMOJI['checkin']} +{DAILY_CHECKIN_REWARD} {EMOJI['points']} points. See you tomorrow!"),
                ephemeral=True,
            )
        else:
            await interaction.response.send_message(
                embed=warning_embed("Already Checked In", "You already checked in today. Come back tomorrow."),
                ephemeral=True,
            )

    @bot.tree.command(name="complete_task", description="Complete a basic task by task ID")
    async def complete_task_command(interaction: discord.Interaction, task_id: int):
        await ensure_user(bot.db, interaction.user)
        task, status = await complete_task(bot.db, interaction.user.id, task_id)

        if status == "TASK_NOT_FOUND":
            await interaction.response.send_message(
                embed=error_embed("Task Not Found", f"No active task with ID #{task_id}. Use `/tasks` to see the list."),
                ephemeral=True,
            )
        elif status == "NOT_SELF_SERVE":
            if is_review_enabled():
                hint = f"Use `/submit_task task_id:{task_id}` with a link/description and/or a screenshot to send it for admin review."
            else:
                hint = "Complete it and contact an admin for review."
            await interaction.response.send_message(
                embed=warning_embed(
                    "Admin Review Required",
                    f"**{task['name']}** is an advanced task and can't be self-claimed. {hint}",
                ),
                ephemeral=True,
            )
        elif status == "NOT_STARTED":
            await interaction.response.send_message(
                embed=warning_embed("Not Started Yet", f"**{task['name']}** hasn't started yet. Check `/tasks` for the start time."),
                ephemeral=True,
            )
        elif status == "EXPIRED":
            await interaction.response.send_message(
                embed=warning_embed("Task Ended", f"**{task['name']}** is no longer accepting completions."),
                ephemeral=True,
            )
        elif status == "ALREADY_DONE":
            await interaction.response.send_message(
                embed=warning_embed("Already Completed", f"You already completed **{task['name']}**."),
                ephemeral=True,
            )
        else:
            await interaction.response.send_message(
                embed=success_embed("Task Completed", f"{EMOJI['task']} **{task['name']}**\n+{task['reward']} {EMOJI['points']} points"),
                ephemeral=True,
            )

    # Advanced-task review queue depends on a configured channel (TASK_REVIEW_CHANNEL_ID).
    # The command is only registered when that configuration is present, so it stays hidden until enabled.
    if is_review_enabled():
        @bot.tree.command(name="submit_task", description="Submit proof for an advanced task for admin review")
        @app_commands.describe(
            proof="A link or description of your proof (optional if attaching a screenshot)",
            screenshot="A screenshot/image as proof (optional if providing a link/description)",
        )
        @app_commands.checks.cooldown(1, 15.0)
        async def submit_task(
            interaction: discord.Interaction,
            task_id: int,
            proof: str = "",
            screenshot: discord.Attachment | None = None,
        ):
            if not proof.strip() and screenshot is None:
                await interaction.response.send_message(
                    embed=error_embed("Proof Required", "Provide a link/description, attach a screenshot, or both."),
                    ephemeral=True,
                )
                return

            await ensure_user(bot.db, interaction.user)
            image_url = screenshot.url if screenshot else None
            task, submission, status = await create_submission(
                bot.db, interaction.user.id, task_id, proof.strip() or None, image_url
            )

            if status == "TASK_NOT_FOUND":
                await interaction.response.send_message(
                    embed=error_embed("Task Not Found", f"No active task with ID #{task_id}."), ephemeral=True
                )
                return
            if status == "NOT_ADVANCED":
                await interaction.response.send_message(
                    embed=warning_embed(
                        "Not Needed", f"**{task['name']}** is a basic task — use `/complete_task task_id:{task_id}` instead."
                    ),
                    ephemeral=True,
                )
                return
            if status == "NOT_STARTED":
                await interaction.response.send_message(
                    embed=warning_embed("Not Started Yet", f"**{task['name']}** hasn't started yet."), ephemeral=True
                )
                return
            if status == "EXPIRED":
                await interaction.response.send_message(
                    embed=warning_embed("Task Ended", f"**{task['name']}** is no longer accepting submissions."), ephemeral=True
                )
                return
            if status == "ALREADY_DONE":
                await interaction.response.send_message(
                    embed=warning_embed("Already Completed", f"You already completed **{task['name']}**."), ephemeral=True
                )
                return
            if status == "ALREADY_PENDING":
                await interaction.response.send_message(
                    embed=warning_embed(
                        "Already Submitted",
                        f"You already have a pending submission for **{task['name']}**. Please wait for review.",
                    ),
                    ephemeral=True,
                )
                return

            channel = bot.get_channel(TASK_REVIEW_CHANNEL_ID) or await bot.fetch_channel(TASK_REVIEW_CHANNEL_ID)
            embed = build_review_embed(submission, task["name"], task["reward"], task["reward_max"])
            view = discord.ui.View(timeout=None)
            view.add_item(ApproveSubmissionButton(submission["id"]))
            view.add_item(RejectSubmissionButton(submission["id"]))
            message = await channel.send(embed=embed, view=view)
            await set_submission_message(bot.db, submission["id"], message.id)

            await interaction.response.send_message(
                embed=success_embed(
                    "Submitted",
                    f"Your submission for **{task['name']}** was sent for review. You'll be notified once it's approved or rejected.",
                ),
                ephemeral=True,
            )
