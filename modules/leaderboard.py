from __future__ import annotations


async def top_points(db, limit: int = 10):
    return await db.fetch(
        '''
        SELECT discord_id, COALESCE(SUM(amount), 0) AS total
        FROM points
        GROUP BY discord_id
        HAVING COALESCE(SUM(amount), 0) > 0
        ORDER BY total DESC
        LIMIT $1
        ''',
        int(limit),
    )


async def top_inviters(db, limit: int = 10):
    return await db.fetch(
        '''
        SELECT inviter_discord_id, COUNT(*) FILTER (WHERE rewarded = true) AS rewarded_count
        FROM referrals
        GROUP BY inviter_discord_id
        HAVING COUNT(*) FILTER (WHERE rewarded = true) > 0
        ORDER BY rewarded_count DESC
        LIMIT $1
        ''',
        int(limit),
    )
