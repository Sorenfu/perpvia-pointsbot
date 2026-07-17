from __future__ import annotations

import discord
from discord import app_commands
from discord.ext import commands
from modules.admin import is_admin, log_admin
from modules.users import ensure_user
from modules.points import add_points
from modules.tasks import (
    create_task,
    edit_task,
    remove_task,
    list_all_tasks,
    grant_task,
    revoke_task_grant,
    parse_task_datetime,
    task_window_text,
    category_label,
    reward_text,
    list_pending_submissions,
    CATEGORY_BASIC,
    CATEGORY_ADVANCED,
)
from modules.shop import create_product, edit_product, remove_product, list_all_products
from modules.ui import EMOJI, error_embed, info_embed, success_embed, paginate_footer, send_paginated

ADMIN_LIST_PAGE_SIZE = 8
CATEGORY_CHOICES = [
    app_commands.Choice(name="Basic (self-serve)", value=CATEGORY_BASIC),
    app_commands.Choice(name="Advanced (admin-reviewed)", value=CATEGORY_ADVANCED),
]


def admin_only(interaction: discord.Interaction) -> bool:
    return is_admin(interaction.user)


def stock_text(stock: int | None) -> str:
    return "Unlimited" if stock is None else str(stock)


def status_text(status: str) -> str:
    return "🟢 ACTIVE" if status == "ACTIVE" else "🔴 INACTIVE"


async def setup(bot: commands.Bot):
    async def deny(interaction: discord.Interaction):
        await interaction.response.send_message(
            embed=error_embed("No Permission", "You are not authorized to use this command."),
            ephemeral=True,
        )

    @bot.tree.command(name="admin_add_points", description="Admin: add points to a user")
    async def admin_add_points(interaction: discord.Interaction, member: discord.Member, amount: int, reason: str = "Admin reward"):
        if not admin_only(interaction):
            await deny(interaction)
            return
        await ensure_user(bot.db, member)
        await add_points(bot.db, member.id, int(amount), "ADMIN_REWARD", reason)
        await log_admin(bot.db, interaction.user.id, "ADMIN_ADD_POINTS", f"{member.id} {amount} {reason}")
        await interaction.response.send_message(
            embed=success_embed("Points Granted", f"Added **{amount}** {EMOJI['points']} points to {member.mention}.\nReason: {reason}"),
            ephemeral=True,
        )

    @bot.tree.command(name="admin_add_task", description="Admin: create a task")
    @app_commands.describe(
        reward="Fixed reward, or the minimum if reward_max is set",
        category="Basic = self-serve /complete_task. Advanced = admin must grant it manually.",
        starts_at="Optional start time, Beijing time, format: YYYY-MM-DD HH:MM",
        ends_at="Optional end time, Beijing time, format: YYYY-MM-DD HH:MM",
        reward_max="Optional: turns reward into a range (reward-reward_max), scored at approval time",
    )
    @app_commands.choices(category=CATEGORY_CHOICES)
    async def admin_add_task(
        interaction: discord.Interaction,
        name: str,
        reward: int,
        description: str = "",
        category: app_commands.Choice[str] | None = None,
        starts_at: str = "",
        ends_at: str = "",
        reward_max: int | None = None,
    ):
        if not admin_only(interaction):
            await deny(interaction)
            return
        try:
            starts_dt = parse_task_datetime(starts_at)
            ends_dt = parse_task_datetime(ends_at)
        except ValueError as exc:
            await interaction.response.send_message(embed=error_embed("Invalid Date", str(exc)), ephemeral=True)
            return
        if reward_max is not None and reward_max < reward:
            await interaction.response.send_message(
                embed=error_embed("Invalid Reward Range", "reward_max must be greater than or equal to reward."),
                ephemeral=True,
            )
            return

        cat_value = category.value if category else CATEGORY_BASIC
        task = await create_task(bot.db, name, reward, description, cat_value, starts_dt, ends_dt, reward_max)
        await log_admin(bot.db, interaction.user.id, "ADMIN_ADD_TASK", f"{task['id']} {name} {reward}-{reward_max} {cat_value}")
        await interaction.response.send_message(
            embed=success_embed(
                "Task Created",
                f"{EMOJI['task']} #{task['id']} **{name}** - {reward_text(reward, reward_max)} points\n"
                f"{category_label(cat_value)} • {task_window_text(task)}",
            ),
            ephemeral=True,
        )

    @bot.tree.command(name="admin_edit_task", description="Admin: edit an existing task")
    @app_commands.describe(
        reward="Fixed reward, or the minimum if reward_max is set",
        category="Basic = self-serve /complete_task. Advanced = admin must grant it manually.",
        starts_at="Optional start time, Beijing time, format: YYYY-MM-DD HH:MM",
        ends_at="Optional end time, Beijing time, format: YYYY-MM-DD HH:MM",
        reward_max="Optional: turns reward into a range (reward-reward_max), scored at approval time",
    )
    @app_commands.choices(category=CATEGORY_CHOICES)
    async def admin_edit_task(
        interaction: discord.Interaction,
        task_id: int,
        name: str,
        reward: int,
        description: str = "",
        category: app_commands.Choice[str] | None = None,
        starts_at: str = "",
        ends_at: str = "",
        reward_max: int | None = None,
    ):
        if not admin_only(interaction):
            await deny(interaction)
            return
        try:
            starts_dt = parse_task_datetime(starts_at)
            ends_dt = parse_task_datetime(ends_at)
        except ValueError as exc:
            await interaction.response.send_message(embed=error_embed("Invalid Date", str(exc)), ephemeral=True)
            return
        if reward_max is not None and reward_max < reward:
            await interaction.response.send_message(
                embed=error_embed("Invalid Reward Range", "reward_max must be greater than or equal to reward."),
                ephemeral=True,
            )
            return

        cat_value = category.value if category else CATEGORY_BASIC
        task = await edit_task(bot.db, task_id, name, reward, description, cat_value, starts_dt, ends_dt, reward_max)
        if not task:
            await interaction.response.send_message(
                embed=error_embed("Task Not Found", f"No active task with ID #{task_id}."), ephemeral=True
            )
            return
        await log_admin(bot.db, interaction.user.id, "ADMIN_EDIT_TASK", f"{task_id} {name} {reward}-{reward_max} {cat_value}")
        await interaction.response.send_message(
            embed=success_embed(
                "Task Updated",
                f"{EMOJI['task']} #{task['id']} **{name}** - {reward_text(reward, reward_max)} points\n"
                f"{category_label(cat_value)} • {task_window_text(task)}",
            ),
            ephemeral=True,
        )

    @bot.tree.command(name="admin_grant_task", description="Admin: manually grant a task's reward to a member (after review)")
    @app_commands.describe(amount="Optional: override the task's base reward, e.g. score a UGC submission higher/lower")
    async def admin_grant_task(
        interaction: discord.Interaction, task_id: int, member: discord.Member, note: str = "", amount: int | None = None
    ):
        if not admin_only(interaction):
            await deny(interaction)
            return
        await ensure_user(bot.db, member)
        task, status = await grant_task(bot.db, interaction.user.id, member.id, task_id, note or None, amount)
        if status == "TASK_NOT_FOUND":
            await interaction.response.send_message(
                embed=error_embed("Task Not Found", f"No active task with ID #{task_id}."), ephemeral=True
            )
            return
        if status == "ALREADY_DONE":
            await interaction.response.send_message(
                embed=error_embed("Already Granted", f"{member.mention} already completed **{task['name']}**."),
                ephemeral=True,
            )
            return
        award_amount = amount if amount is not None else task["reward"]
        await log_admin(bot.db, interaction.user.id, "ADMIN_GRANT_TASK", f"{task_id} {member.id} amount={award_amount} {note}")
        await interaction.response.send_message(
            embed=success_embed(
                "Task Granted",
                f"{EMOJI['task']} Granted **{task['name']}** to {member.mention}\n+{award_amount} {EMOJI['points']} points",
            ),
            ephemeral=True,
        )

    @bot.tree.command(name="admin_revoke_grant", description="Admin: undo a member's task completion and claw back the points")
    async def admin_revoke_grant(interaction: discord.Interaction, task_id: int, member: discord.Member):
        if not admin_only(interaction):
            await deny(interaction)
            return
        task, status = await revoke_task_grant(bot.db, member.id, task_id)
        if status == "NOT_FOUND":
            await interaction.response.send_message(
                embed=error_embed("Nothing To Revoke", f"{member.mention} hasn't completed task #{task_id}."),
                ephemeral=True,
            )
            return
        await log_admin(bot.db, interaction.user.id, "ADMIN_REVOKE_GRANT", f"{task_id} {member.id}")
        task_name = task["name"] if task else f"#{task_id}"
        await interaction.response.send_message(
            embed=success_embed("Grant Revoked", f"Revoked **{task_name}** from {member.mention} and clawed back the points."),
            ephemeral=True,
        )

    @bot.tree.command(name="admin_pending_tasks", description="Admin: list pending advanced-task submissions")
    async def admin_pending_tasks(interaction: discord.Interaction):
        if not admin_only(interaction):
            await deny(interaction)
            return
        rows = await list_pending_submissions(bot.db)
        if not rows:
            await interaction.response.send_message(
                embed=info_embed(f"{EMOJI['task']} Pending Submissions", "Nothing pending review right now."), ephemeral=True
            )
            return

        chunks = [rows[i : i + ADMIN_LIST_PAGE_SIZE] for i in range(0, len(rows), ADMIN_LIST_PAGE_SIZE)]
        pages = []
        for page_num, chunk in enumerate(chunks, start=1):
            embed = info_embed(f"{EMOJI['task']} Pending Submissions")
            for s in chunk:
                proof = s["proof"] or ("Screenshot only, see link below." if s["proof_image_url"] else "No proof provided.")
                screenshot_line = f"\n[View screenshot]({s['proof_image_url']})" if s["proof_image_url"] else ""
                embed.add_field(
                    name=f"#{s['id']} · {s['task_name']} ({reward_text(s['task_reward'], s['task_reward_max'])} {EMOJI['points']})",
                    value=(
                        f"By: <@{s['discord_id']}>\nProof: {proof}{screenshot_line}\nSubmitted: {s['created_at']}\n"
                        f"Use `/admin_grant_task task_id:{s['task_id']} member:<user>` to approve manually, "
                        f"or review it in the submissions channel."
                    ),
                    inline=False,
                )
            paginate_footer(embed, page_num, len(chunks))
            pages.append(embed)
        await send_paginated(interaction, pages)

    @bot.tree.command(name="admin_remove_task", description="Admin: remove a task")
    async def admin_remove_task(interaction: discord.Interaction, task_id: int):
        if not admin_only(interaction):
            await deny(interaction)
            return
        task = await remove_task(bot.db, task_id)
        if not task:
            await interaction.response.send_message(
                embed=error_embed("Task Not Found", f"No active task with ID #{task_id}."), ephemeral=True
            )
            return
        await log_admin(bot.db, interaction.user.id, "ADMIN_REMOVE_TASK", f"{task_id}")
        await interaction.response.send_message(
            embed=success_embed("Task Removed", f"Task #{task_id} **{task['name']}** is now inactive."),
            ephemeral=True,
        )

    @bot.tree.command(name="admin_list_tasks", description="Admin: list all tasks including inactive")
    async def admin_list_tasks(interaction: discord.Interaction):
        if not admin_only(interaction):
            await deny(interaction)
            return
        rows = await list_all_tasks(bot.db)
        if not rows:
            await interaction.response.send_message(
                embed=info_embed(f"{EMOJI['task']} All Tasks", "No tasks yet."), ephemeral=True
            )
            return

        chunks = [rows[i : i + ADMIN_LIST_PAGE_SIZE] for i in range(0, len(rows), ADMIN_LIST_PAGE_SIZE)]
        pages = []
        for page_num, chunk in enumerate(chunks, start=1):
            embed = info_embed(f"{EMOJI['task']} All Tasks")
            for t in chunk:
                desc = t["description"] or "No description"
                embed.add_field(
                    name=f"#{t['id']} · {t['name']} · {status_text(t['status'])}",
                    value=f"{reward_text(t['reward'], t['reward_max'])} {EMOJI['points']} points\n{desc}\n{category_label(t['category'])} • {task_window_text(t)}",
                    inline=False,
                )
            paginate_footer(embed, page_num, len(chunks))
            pages.append(embed)
        await send_paginated(interaction, pages)

    @bot.tree.command(name="admin_add_product", description="Admin: create a shop product")
    @app_commands.describe(requires_wallet="If true, redeemers must have (or submit) an EVM wallet address")
    async def admin_add_product(
        interaction: discord.Interaction,
        name: str,
        price: int,
        role: discord.Role | None = None,
        description: str = "",
        stock: int | None = None,
        requires_wallet: bool = False,
    ):
        if not admin_only(interaction):
            await deny(interaction)
            return
        product = await create_product(bot.db, name, price, role.id if role else None, description, stock, requires_wallet)
        await log_admin(bot.db, interaction.user.id, "ADMIN_ADD_PRODUCT", f"{product['id']} {name} {price}")
        await interaction.response.send_message(
            embed=success_embed(
                "Product Created",
                f"{EMOJI['shop']} #{product['id']} **{name}** - {price} {EMOJI['points']}\n"
                f"Stock: {stock_text(stock)} • Requires wallet: {'Yes' if requires_wallet else 'No'}",
            ),
            ephemeral=True,
        )

    @bot.tree.command(name="admin_edit_product", description="Admin: edit an existing shop product")
    @app_commands.describe(requires_wallet="If true, redeemers must have (or submit) an EVM wallet address")
    async def admin_edit_product(
        interaction: discord.Interaction,
        product_id: int,
        name: str,
        price: int,
        role: discord.Role | None = None,
        description: str = "",
        stock: int | None = None,
        requires_wallet: bool = False,
    ):
        if not admin_only(interaction):
            await deny(interaction)
            return
        product = await edit_product(bot.db, product_id, name, price, role.id if role else None, description, stock, requires_wallet)
        if not product:
            await interaction.response.send_message(
                embed=error_embed("Product Not Found", f"No active product with ID #{product_id}."), ephemeral=True
            )
            return
        await log_admin(bot.db, interaction.user.id, "ADMIN_EDIT_PRODUCT", f"{product_id} {name} {price}")
        await interaction.response.send_message(
            embed=success_embed(
                "Product Updated",
                f"{EMOJI['shop']} #{product['id']} **{name}** - {price} {EMOJI['points']}\n"
                f"Stock: {stock_text(stock)} • Requires wallet: {'Yes' if requires_wallet else 'No'}",
            ),
            ephemeral=True,
        )

    @bot.tree.command(name="admin_remove_product", description="Admin: remove a shop product")
    async def admin_remove_product(interaction: discord.Interaction, product_id: int):
        if not admin_only(interaction):
            await deny(interaction)
            return
        product = await remove_product(bot.db, product_id)
        if not product:
            await interaction.response.send_message(
                embed=error_embed("Product Not Found", f"No active product with ID #{product_id}."), ephemeral=True
            )
            return
        await log_admin(bot.db, interaction.user.id, "ADMIN_REMOVE_PRODUCT", f"{product_id}")
        await interaction.response.send_message(
            embed=success_embed("Product Removed", f"Product #{product_id} **{product['name']}** is now inactive."),
            ephemeral=True,
        )

    @bot.tree.command(name="admin_list_products", description="Admin: list all products including inactive")
    async def admin_list_products(interaction: discord.Interaction):
        if not admin_only(interaction):
            await deny(interaction)
            return
        rows = await list_all_products(bot.db)
        if not rows:
            await interaction.response.send_message(
                embed=info_embed(f"{EMOJI['shop']} All Products", "No products yet."), ephemeral=True
            )
            return

        chunks = [rows[i : i + ADMIN_LIST_PAGE_SIZE] for i in range(0, len(rows), ADMIN_LIST_PAGE_SIZE)]
        pages = []
        for page_num, chunk in enumerate(chunks, start=1):
            embed = info_embed(f"{EMOJI['shop']} All Products")
            for p in chunk:
                desc = p["description"] or "No description"
                role_text = f"Role: <@&{p['role_id']}>" if p["role_id"] else "No role"
                wallet_text = " • 🔑 Requires wallet" if p["requires_wallet"] else ""
                embed.add_field(
                    name=f"#{p['id']} · {p['name']} · {status_text(p['status'])} — {p['price']} {EMOJI['points']}",
                    value=f"{desc}\n{role_text} • Stock: {stock_text(p['stock'])}{wallet_text}",
                    inline=False,
                )
            paginate_footer(embed, page_num, len(chunks))
            pages.append(embed)
        await send_paginated(interaction, pages)

    @bot.tree.command(name="admin_stats", description="Admin: show community stats")
    async def admin_stats(interaction: discord.Interaction):
        if not admin_only(interaction):
            await deny(interaction)
            return
        users = await bot.db.fetchval("SELECT COUNT(*) FROM users")
        points = await bot.db.fetchval("SELECT COALESCE(SUM(amount), 0) FROM points")
        active_today = await bot.db.fetchval(
            "SELECT COUNT(DISTINCT discord_id) FROM message_activity WHERE activity_date = CURRENT_DATE"
        )
        active_7d = await bot.db.fetchval(
            "SELECT COUNT(DISTINCT discord_id) FROM message_activity WHERE activity_date >= CURRENT_DATE - INTERVAL '6 days'"
        )
        tasks = await bot.db.fetchval("SELECT COUNT(*) FROM tasks WHERE status='ACTIVE'")
        products = await bot.db.fetchval("SELECT COUNT(*) FROM products WHERE status='ACTIVE'")
        orders = await bot.db.fetchval("SELECT COUNT(*) FROM orders")
        points_spent = await bot.db.fetchval("SELECT COALESCE(SUM(price), 0) FROM orders WHERE status='SUCCESS'")
        referrals = await bot.db.fetchval("SELECT COUNT(*) FROM referrals")
        pending_referrals = await bot.db.fetchval("SELECT COUNT(*) FROM referrals WHERE rewarded=false")

        embed = info_embed(f"{EMOJI['admin']} Community Stats")
        embed.add_field(name="Users", value=str(users), inline=True)
        embed.add_field(name=f"{EMOJI['points']} Points Total", value=str(points), inline=True)
        embed.add_field(name="​", value="​", inline=True)
        embed.add_field(name="Active Today", value=str(active_today), inline=True)
        embed.add_field(name="Active (7d)", value=str(active_7d), inline=True)
        embed.add_field(name="​", value="​", inline=True)
        embed.add_field(name=f"{EMOJI['task']} Active Tasks", value=str(tasks), inline=True)
        embed.add_field(name=f"{EMOJI['shop']} Active Products", value=str(products), inline=True)
        embed.add_field(name="​", value="​", inline=True)
        embed.add_field(name="Orders", value=str(orders), inline=True)
        embed.add_field(name=f"{EMOJI['points']} Points Spent", value=str(points_spent), inline=True)
        embed.add_field(name="​", value="​", inline=True)
        embed.add_field(name=f"{EMOJI['invite']} Referrals", value=str(referrals), inline=True)
        embed.add_field(name="Pending Referrals", value=str(pending_referrals), inline=True)
        await interaction.response.send_message(embed=embed, ephemeral=True)
