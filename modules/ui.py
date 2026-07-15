from __future__ import annotations

import discord

COLOR_PRIMARY = 0x5865F2
COLOR_SUCCESS = 0x57F287
COLOR_ERROR = 0xED4245
COLOR_WARNING = 0xFEE75C
COLOR_GOLD = 0xF1C40F

EMOJI = {
    "points": "\U0001F4B0",
    "task": "\U0001F3AF",
    "checkin": "\U0001F5D3",
    "shop": "\U0001F6D2",
    "reward": "\U0001F381",
    "invite": "\U0001F4E8",
    "leaderboard": "\U0001F3C6",
    "admin": "⚙️",
    "success": "✅",
    "error": "❌",
    "warning": "⚠️",
    "profile": "\U0001F9FE",
    "sold_out": "\U0001F6AB",
    "medal": ["\U0001F947", "\U0001F948", "\U0001F949"],
}

FOOTER_TEXT = "Community OS Lite"


def base_embed(title: str, description: str | None = None, color: int = COLOR_PRIMARY) -> discord.Embed:
    embed = discord.Embed(title=title, description=description, color=color)
    embed.set_footer(text=FOOTER_TEXT)
    return embed


def success_embed(title: str, description: str | None = None) -> discord.Embed:
    return base_embed(f"{EMOJI['success']} {title}", description, COLOR_SUCCESS)


def error_embed(title: str, description: str | None = None) -> discord.Embed:
    return base_embed(f"{EMOJI['error']} {title}", description, COLOR_ERROR)


def warning_embed(title: str, description: str | None = None) -> discord.Embed:
    return base_embed(f"{EMOJI['warning']} {title}", description, COLOR_WARNING)


def info_embed(title: str, description: str | None = None) -> discord.Embed:
    return base_embed(title, description, COLOR_PRIMARY)


def rank_prefix(index: int) -> str:
    medals = EMOJI["medal"]
    if index < len(medals):
        return medals[index]
    return f"`#{index + 1}`"


def paginate_footer(embed: discord.Embed, page: int, total_pages: int) -> None:
    if total_pages > 1:
        embed.set_footer(text=f"{FOOTER_TEXT} • Page {page}/{total_pages}")


class Paginator(discord.ui.View):
    def __init__(self, owner_id: int, embeds: list[discord.Embed], timeout: float = 90):
        super().__init__(timeout=timeout)
        self.owner_id = owner_id
        self.embeds = embeds
        self.index = 0
        self._sync_buttons()

    def _sync_buttons(self) -> None:
        self.previous_page.disabled = self.index == 0
        self.next_page.disabled = self.index >= len(self.embeds) - 1
        self.page_label.label = f"{self.index + 1}/{len(self.embeds)}"

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.owner_id:
            await interaction.response.send_message(
                embed=error_embed("Not Yours", "This menu isn't for you."), ephemeral=True
            )
            return False
        return True

    async def on_timeout(self) -> None:
        for child in self.children:
            child.disabled = True

    @discord.ui.button(label="◀", style=discord.ButtonStyle.secondary)
    async def previous_page(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.index -= 1
        self._sync_buttons()
        await interaction.response.edit_message(embed=self.embeds[self.index], view=self)

    @discord.ui.button(label="1/1", style=discord.ButtonStyle.secondary, disabled=True)
    async def page_label(self, interaction: discord.Interaction, button: discord.ui.Button):
        pass

    @discord.ui.button(label="▶", style=discord.ButtonStyle.secondary)
    async def next_page(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.index += 1
        self._sync_buttons()
        await interaction.response.edit_message(embed=self.embeds[self.index], view=self)


async def send_paginated(interaction: discord.Interaction, embeds: list[discord.Embed], ephemeral: bool = True) -> None:
    if len(embeds) <= 1:
        await interaction.response.send_message(embed=embeds[0], ephemeral=ephemeral)
        return
    view = Paginator(interaction.user.id, embeds)
    await interaction.response.send_message(embed=embeds[0], view=view, ephemeral=ephemeral)
