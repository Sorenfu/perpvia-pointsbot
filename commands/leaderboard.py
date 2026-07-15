from __future__ import annotations

from typing import Optional

import discord
from discord import app_commands
from discord.ext import commands
from modules.leaderboard import top_points, top_inviters
from modules.ui import EMOJI, base_embed, rank_prefix, paginate_footer, send_paginated

LEADERBOARD_PAGE_SIZE = 10
LEADERBOARD_MAX_ROWS = 50


def format_points_lines(rows, start_rank: int = 0) -> str:
    if not rows:
        return "No points recorded yet."
    return "\n".join(
        f"{rank_prefix(start_rank + i)} <@{row['discord_id']}> — **{row['total']}** {EMOJI['points']}"
        for i, row in enumerate(rows)
    )


def format_invite_lines(rows, start_rank: int = 0) -> str:
    if not rows:
        return "No rewarded invites yet."
    return "\n".join(
        f"{rank_prefix(start_rank + i)} <@{row['inviter_discord_id']}> — **{row['rewarded_count']}** {EMOJI['invite']}"
        for i, row in enumerate(rows)
    )


def build_leaderboard_pages(rows, formatter, title: str, field_name: str) -> list[discord.Embed]:
    if not rows:
        embed = base_embed(title)
        embed.add_field(name=field_name, value=formatter([]), inline=False)
        return [embed]

    chunks = [rows[i : i + LEADERBOARD_PAGE_SIZE] for i in range(0, len(rows), LEADERBOARD_PAGE_SIZE)]
    pages = []
    for page_num, chunk in enumerate(chunks, start=1):
        embed = base_embed(title)
        embed.add_field(name=field_name, value=formatter(chunk, (page_num - 1) * LEADERBOARD_PAGE_SIZE), inline=False)
        paginate_footer(embed, page_num, len(chunks))
        pages.append(embed)
    return pages


async def setup(bot: commands.Bot):
    @bot.tree.command(name="leaderboard", description="Show community leaderboards")
    @app_commands.describe(board="Which leaderboard to show")
    @app_commands.choices(
        board=[
            app_commands.Choice(name="Overall", value="overall"),
            app_commands.Choice(name="Points", value="points"),
            app_commands.Choice(name="Invites", value="invites"),
        ]
    )
    async def leaderboard(interaction: discord.Interaction, board: Optional[app_commands.Choice[str]] = None):
        choice = board.value if board else "overall"

        if choice == "points":
            rows = await top_points(bot.db, LEADERBOARD_MAX_ROWS)
            pages = build_leaderboard_pages(
                rows, format_points_lines, f"{EMOJI['leaderboard']} Points Leaderboard", f"{EMOJI['points']} Top Points"
            )
            await send_paginated(interaction, pages)
        elif choice == "invites":
            rows = await top_inviters(bot.db, LEADERBOARD_MAX_ROWS)
            pages = build_leaderboard_pages(
                rows, format_invite_lines, f"{EMOJI['leaderboard']} Invite Leaderboard", f"{EMOJI['invite']} Top Inviters"
            )
            await send_paginated(interaction, pages)
        else:
            points_rows = await top_points(bot.db, 5)
            invite_rows = await top_inviters(bot.db, 5)
            embed = base_embed(f"{EMOJI['leaderboard']} Community Leaderboard")
            embed.add_field(name=f"{EMOJI['points']} Top Points", value=format_points_lines(points_rows), inline=True)
            embed.add_field(name=f"{EMOJI['invite']} Top Inviters", value=format_invite_lines(invite_rows), inline=True)
            await interaction.response.send_message(embed=embed, ephemeral=True)
