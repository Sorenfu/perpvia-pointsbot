from __future__ import annotations

import discord
from modules.points import add_points

INVITER_REWARD = 20
INVITEE_REWARD = 10


async def refresh_guild_invites(bot, guild: discord.Guild):
    try:
        invites = await guild.invites()
        bot.invite_cache[guild.id] = {invite.code: invite.uses or 0 for invite in invites}
    except discord.Forbidden:
        bot.invite_cache[guild.id] = {}
    except Exception:
        bot.invite_cache[guild.id] = {}


async def store_invite(db, code: str, inviter_discord_id: int, uses: int = 0):
    await db.execute(
        '''
        INSERT INTO invite_codes (code, inviter_discord_id, uses)
        VALUES ($1, $2, $3)
        ON CONFLICT (code)
        DO UPDATE SET inviter_discord_id=EXCLUDED.inviter_discord_id, uses=EXCLUDED.uses
        ''',
        code,
        int(inviter_discord_id),
        int(uses or 0),
    )


async def get_latest_invite_code(db, inviter_discord_id: int) -> str | None:
    """Return the most recently created invite code we've stored for this
    user, if any. Used so /invite reuses one link per person instead of
    minting a new one every time (which would otherwise pile up invites in
    the server, up to Discord's per-guild cap)."""
    row = await db.fetchrow(
        "SELECT code FROM invite_codes WHERE inviter_discord_id=$1 ORDER BY created_at DESC LIMIT 1",
        int(inviter_discord_id),
    )
    return row["code"] if row else None


async def handle_member_join(bot, member: discord.Member):
    guild = member.guild
    before = bot.invite_cache.get(guild.id, {})
    used_code = None

    try:
        after_invites = await guild.invites()
        after = {invite.code: invite.uses or 0 for invite in after_invites}
        for code, uses in after.items():
            if uses > before.get(code, 0):
                used_code = code
                break
        bot.invite_cache[guild.id] = after
    except Exception:
        return

    if not used_code:
        return

    invite_row = await bot.db.fetchrow("SELECT * FROM invite_codes WHERE code=$1", used_code)
    if not invite_row:
        return

    inviter_id = int(invite_row["inviter_discord_id"])
    invitee_id = int(member.id)
    if inviter_id == invitee_id:
        return

    inserted = await bot.db.fetchrow(
        '''
        INSERT INTO referrals (inviter_discord_id, invitee_discord_id, invite_code)
        VALUES ($1, $2, $3)
        ON CONFLICT (invitee_discord_id)
        DO NOTHING
        RETURNING id
        ''',
        inviter_id,
        invitee_id,
        used_code,
    )
    if inserted is not None and hasattr(bot, "pending_referral_ids"):
        bot.pending_referral_ids.add(invitee_id)


async def process_message_for_referral(db, invitee_discord_id: int):
    referral = await db.fetchrow(
        '''
        SELECT * FROM referrals
        WHERE invitee_discord_id=$1 AND rewarded=false
        ''',
        int(invitee_discord_id),
    )
    if not referral:
        return False

    inviter_id = int(referral["inviter_discord_id"])
    if inviter_id == int(invitee_discord_id):
        return False

    await add_points(db, inviter_id, INVITER_REWARD, "REFERRAL", f"Referral reward for {invitee_discord_id}")
    await add_points(db, invitee_discord_id, INVITEE_REWARD, "WELCOME", "Welcome referral reward")
    await db.execute(
        '''
        UPDATE referrals
        SET verified=true, rewarded=true, rewarded_at=NOW()
        WHERE id=$1
        ''',
        int(referral["id"]),
    )
    return True


async def get_pending_referral_invitee_ids(db) -> set[int]:
    """Invitees who still owe a first-message reward. Used to build an
    in-memory fast-path so we don't hit the DB on every single message."""
    rows = await db.fetch("SELECT invitee_discord_id FROM referrals WHERE rewarded=false")
    return {int(r["invitee_discord_id"]) for r in rows}


async def referral_stats(db, discord_id: int):
    total = await db.fetchval("SELECT COUNT(*) FROM referrals WHERE inviter_discord_id=$1", int(discord_id))
    rewarded = await db.fetchval("SELECT COUNT(*) FROM referrals WHERE inviter_discord_id=$1 AND rewarded=true", int(discord_id))
    return int(total or 0), int(rewarded or 0)
