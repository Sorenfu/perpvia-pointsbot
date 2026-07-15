from __future__ import annotations

import discord
from discord import app_commands
from discord.ext import commands

from config import NFT_HOLDER_ROLE_ID
from modules.users import ensure_user
from modules.wallet import is_valid_address, start_binding, confirm_binding, get_wallet, unbind_wallet
from modules.nft import is_enabled as nft_enabled, get_nft_balance
from modules.ui import EMOJI, base_embed, error_embed, success_embed, info_embed


async def setup(bot: commands.Bot):
    @bot.tree.command(name="wallet_bind", description="Start wallet verification by binding an EVM wallet address")
    @app_commands.checks.cooldown(1, 10.0)
    async def wallet_bind(interaction: discord.Interaction, address: str):
        await ensure_user(bot.db, interaction.user)
        address = address.strip()
        if not is_valid_address(address):
            await interaction.response.send_message(
                embed=error_embed("Invalid Address", "Please provide a valid EVM address, e.g. `0xAbC123...`."),
                ephemeral=True,
            )
            return

        message = await start_binding(bot.db, interaction.user.id, address)
        embed = base_embed(
            f"{EMOJI['profile']} Verify Wallet Ownership",
            (
                "Sign the message below with your wallet (e.g. your wallet app's \"Sign Message\" feature), "
                "then run `/wallet_confirm signature:<your signature>`.\n\n"
                f"```\n{message}\n```\n"
                "This does not authorize any transaction and expires in 10 minutes."
            ),
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @bot.tree.command(name="wallet_confirm", description="Confirm wallet ownership with a signed message")
    @app_commands.checks.cooldown(1, 10.0)
    async def wallet_confirm(interaction: discord.Interaction, signature: str):
        ok, result = await confirm_binding(bot.db, interaction.user.id, signature.strip())
        if not ok:
            await interaction.response.send_message(embed=error_embed("Verification Failed", result), ephemeral=True)
            return

        await interaction.response.send_message(
            embed=success_embed("Wallet Verified", f"Bound wallet `{result}` to your account."), ephemeral=True
        )

    @bot.tree.command(name="wallet_status", description="Show your bound wallet address")
    async def wallet_status(interaction: discord.Interaction):
        row = await get_wallet(bot.db, interaction.user.id)
        if not row:
            await interaction.response.send_message(
                embed=info_embed("No Wallet Bound", "Use `/wallet_bind` to verify a wallet."), ephemeral=True
            )
            return
        embed = base_embed(f"{EMOJI['profile']} Wallet Status")
        embed.add_field(name="Address", value=f"`{row['wallet_address']}`", inline=False)
        embed.add_field(name="Verified At", value=str(row["verified_at"]), inline=False)
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @bot.tree.command(name="wallet_unbind", description="Remove your bound wallet")
    async def wallet_unbind(interaction: discord.Interaction):
        removed = await unbind_wallet(bot.db, interaction.user.id)
        if removed:
            await interaction.response.send_message(
                embed=success_embed("Wallet Unbound", "Your wallet has been unlinked."), ephemeral=True
            )
        else:
            await interaction.response.send_message(
                embed=info_embed("No Wallet Bound", "You don't have a wallet bound yet."), ephemeral=True
            )

    # NFT holder checks depend on a configured contract + RPC endpoint (NFT_CONTRACT_ADDRESS / NFT_RPC_URL).
    # The command is only registered when that configuration is present, so it stays hidden until enabled.
    if nft_enabled():
        @bot.tree.command(name="wallet_holdings", description="Check your NFT holdings and sync the holder role")
        @app_commands.checks.cooldown(1, 15.0)
        async def wallet_holdings(interaction: discord.Interaction):
            if not isinstance(interaction.user, discord.Member):
                await interaction.response.send_message(
                    embed=error_embed("Server Only", "This command must be used inside a server."), ephemeral=True
                )
                return

            row = await get_wallet(bot.db, interaction.user.id)
            if not row:
                await interaction.response.send_message(
                    embed=error_embed("No Wallet Bound", "Use `/wallet_bind` first."), ephemeral=True
                )
                return

            await interaction.response.defer(ephemeral=True)
            try:
                balance = await get_nft_balance(row["wallet_address"])
            except Exception as exc:
                await interaction.followup.send(
                    embed=error_embed("Lookup Failed", f"Could not read chain data: {exc}"), ephemeral=True
                )
                return

            role_note = ""
            if balance > 0 and NFT_HOLDER_ROLE_ID:
                role = interaction.guild.get_role(NFT_HOLDER_ROLE_ID) if interaction.guild else None
                if role is None:
                    role_note = "\nHolder role is configured but not found on this server."
                else:
                    try:
                        await interaction.user.add_roles(role, reason="NFT holder verification")
                        role_note = f"\nRole granted: {role.name}"
                    except discord.Forbidden:
                        role_note = "\nCould not grant role: bot is missing permission."

            embed = success_embed(
                "Holdings Checked",
                f"Wallet `{row['wallet_address']}` holds **{balance}** NFT(s) from the configured collection.{role_note}",
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
