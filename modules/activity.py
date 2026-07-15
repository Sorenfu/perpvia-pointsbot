from __future__ import annotations

from datetime import date

from modules.points import add_points

MESSAGE_POINT_REWARD = 1
MESSAGE_POINT_COOLDOWN_SECONDS = 60
MESSAGE_POINT_DAILY_CAP = 20


async def award_message_points(db, discord_id: int) -> bool:
    today = date.today()
    async with db.transaction() as conn:
        row = await conn.fetchrow(
            '''
            INSERT INTO message_activity (discord_id, activity_date, points_earned, last_rewarded_at)
            VALUES ($1, $2, $3, NOW())
            ON CONFLICT (discord_id, activity_date)
            DO UPDATE SET
                points_earned = message_activity.points_earned + $3,
                last_rewarded_at = NOW()
            WHERE message_activity.points_earned + $3 <= $4
              AND EXTRACT(EPOCH FROM (NOW() - message_activity.last_rewarded_at)) >= $5
            RETURNING points_earned
            ''',
            int(discord_id),
            today,
            MESSAGE_POINT_REWARD,
            MESSAGE_POINT_DAILY_CAP,
            MESSAGE_POINT_COOLDOWN_SECONDS,
        )
        if not row:
            return False
        await add_points(conn, discord_id, MESSAGE_POINT_REWARD, "MESSAGE_ACTIVITY", "Daily chat activity")
    return True


async def get_today_progress(db, discord_id: int) -> int:
    today = date.today()
    value = await db.fetchval(
        "SELECT points_earned FROM message_activity WHERE discord_id=$1 AND activity_date=$2",
        int(discord_id),
        today,
    )
    return int(value or 0)
