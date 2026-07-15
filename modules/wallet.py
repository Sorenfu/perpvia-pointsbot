from __future__ import annotations

import re
import secrets
from datetime import datetime, timedelta, timezone

import asyncpg
from eth_account import Account
from eth_account.messages import encode_defunct

ADDRESS_RE = re.compile(r"^0x[a-fA-F0-9]{40}$")
NONCE_TTL_MINUTES = 10


def is_valid_address(address: str) -> bool:
    return bool(ADDRESS_RE.match(address))


def build_message(discord_id: int, nonce: str) -> str:
    return (
        "Community OS Wallet Verification\n"
        f"Discord ID: {discord_id}\n"
        f"Nonce: {nonce}\n"
        "This signature only proves wallet ownership and does not authorize any transaction."
    )


async def start_binding(db, discord_id: int, wallet_address: str) -> str:
    nonce = secrets.token_hex(16)
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=NONCE_TTL_MINUTES)
    await db.execute(
        '''
        INSERT INTO wallet_nonces (discord_id, wallet_address, nonce, expires_at, created_at)
        VALUES ($1, $2, $3, $4, NOW())
        ON CONFLICT (discord_id)
        DO UPDATE SET wallet_address=EXCLUDED.wallet_address, nonce=EXCLUDED.nonce, expires_at=EXCLUDED.expires_at, created_at=NOW()
        ''',
        int(discord_id),
        wallet_address.lower(),
        nonce,
        expires_at,
    )
    return build_message(discord_id, nonce)


async def confirm_binding(db, discord_id: int, signature: str) -> tuple[bool, str]:
    row = await db.fetchrow("SELECT * FROM wallet_nonces WHERE discord_id=$1", int(discord_id))
    if not row:
        return False, "No pending wallet verification. Use `/wallet_bind` first."

    if row["expires_at"].replace(tzinfo=timezone.utc) < datetime.now(timezone.utc):
        await db.execute("DELETE FROM wallet_nonces WHERE discord_id=$1", int(discord_id))
        return False, "Verification request expired. Use `/wallet_bind` again."

    message = build_message(discord_id, row["nonce"])
    try:
        encoded = encode_defunct(text=message)
        recovered = Account.recover_message(encoded, signature=signature)
    except Exception:
        return False, "Invalid signature format."

    if recovered.lower() != row["wallet_address"].lower():
        return False, "Signature does not match the wallet address you provided."

    try:
        await db.execute(
            '''
            INSERT INTO wallet_bindings (discord_id, wallet_address, verified_at)
            VALUES ($1, $2, NOW())
            ON CONFLICT (discord_id)
            DO UPDATE SET wallet_address=EXCLUDED.wallet_address, verified_at=NOW()
            ''',
            int(discord_id),
            row["wallet_address"],
        )
    except asyncpg.UniqueViolationError:
        await db.execute("DELETE FROM wallet_nonces WHERE discord_id=$1", int(discord_id))
        return False, "This wallet is already bound to another Discord account."

    await db.execute("DELETE FROM wallet_nonces WHERE discord_id=$1", int(discord_id))
    return True, row["wallet_address"]


async def get_wallet(db, discord_id: int):
    return await db.fetchrow("SELECT * FROM wallet_bindings WHERE discord_id=$1", int(discord_id))


async def unbind_wallet(db, discord_id: int) -> bool:
    result = await db.execute("DELETE FROM wallet_bindings WHERE discord_id=$1", int(discord_id))
    return result.split(" ")[-1] != "0"
