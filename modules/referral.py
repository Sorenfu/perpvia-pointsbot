from database import db
from modules import points

INVITER_REWARD = 20
INVITEE_REWARD = 10

async def save_invite_link(guild_id: int, invite_code: str, inviter_user_id: int):
    await db.execute(
        """
        INSERT INTO invite_links(guild_id, invite_code, inviter_user_id)
        VALUES($1,$2,$3)
        ON CONFLICT(invite_code) DO UPDATE SET inviter_user_id=$3
        """,
        guild_id,
        invite_code,
        inviter_user_id,
    )

async def create_referral(invite_code: str, invitee_user_id: int):
    link = await db.fetchrow("SELECT * FROM invite_links WHERE invite_code=$1", invite_code)
    if not link:
        return None
    inviter_user_id = int(link["inviter_user_id"])
    if inviter_user_id == invitee_user_id:
        return None
    existing = await db.fetchrow("SELECT * FROM referrals WHERE invitee_id=$1", invitee_user_id)
    if existing:
        return existing
    return await db.fetchrow(
        "INSERT INTO referrals(inviter_id, invitee_id, invite_code) VALUES($1,$2,$3) RETURNING *",
        inviter_user_id,
        invitee_user_id,
        invite_code,
    )

async def verify_by_message(invitee_user_id: int, message_content: str) -> tuple[bool, str]:
    if not message_content or len(message_content.strip()) < 5:
        return False, "Message too short."
    ref = await db.fetchrow("SELECT * FROM referrals WHERE invitee_id=$1", invitee_user_id)
    if not ref:
        return False, "No referral found."
    if ref["rewarded"]:
        return False, "Already rewarded."
    await db.execute("UPDATE referrals SET verified=true, rewarded=true, rewarded_at=NOW() WHERE id=$1", ref["id"])
    await points.add_points(int(ref["inviter_id"]), INVITER_REWARD, "REFERRAL_REWARD", "Invite friend")
    await points.add_points(invitee_user_id, INVITEE_REWARD, "WELCOME_REWARD", "Referral welcome bonus")
    return True, "Referral rewarded."

async def get_referral_stats(user_id: int):
    total = await db.fetchval("SELECT COUNT(*) FROM referrals WHERE inviter_id=$1", user_id)
    rewarded = await db.fetchval("SELECT COUNT(*) FROM referrals WHERE inviter_id=$1 AND rewarded=true", user_id)
    return int(total or 0), int(rewarded or 0), int(rewarded or 0) * INVITER_REWARD
