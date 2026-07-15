from __future__ import annotations

import logging

import discord

from config import ERROR_WEBHOOK_URL

log = logging.getLogger("community-os")


async def send_alert(client: discord.Client, title: str, detail: str) -> None:
    if not ERROR_WEBHOOK_URL:
        return
    try:
        webhook = discord.Webhook.from_url(ERROR_WEBHOOK_URL, client=client)
        embed = discord.Embed(
            title=f"\U0001F6A8 {title}",
            description=f"```{detail[:3900]}```",
            color=0xED4245,
        )
        await webhook.send(embed=embed, username="Community OS Alerts")
    except Exception:
        log.exception("Failed to deliver error alert webhook")
