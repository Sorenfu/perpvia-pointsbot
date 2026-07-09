# Community OS Beta 1.0 Single Runtime

This is a simplified production runtime designed for Railway + GitHub deployment.

## Required Railway Variables

```env
DISCORD_TOKEN=
GUILD_ID=1494573358887731232
DATABASE_URL=
REDIS_URL=
ADMIN_USER_IDS=
SHOP_CHANNEL_ID=1519929709914493018
POINT_LOG_CHANNEL_ID=1524658027716804648
ADMIN_LOG_CHANNEL_ID=1524658027716804648
CAMPAIGN_CHANNEL_ID=1501804167201689661
ANNOUNCEMENT_CHANNEL_ID=1501779720449294406
```

## Commands

User:
- `/balance`
- `/daily`
- `/shop`
- `/leaderboard`

Admin:
- `/add_points`
- `/remove_points`
- `/product_create`
- `/product_delete`

## Rules

- Daily: +20 points every 12 hours
- Message reward: +1 point, minimum 10 characters, 60 seconds cooldown, max 50 points/day
- Invite reward: +20 points to inviter after invitee first `/daily`
- Role rewards:
  - Pathfinder: +100
  - Trailblazer: +300
  - Momentum Maker: +500
  - Via Elite: +1000
- Shop default exchange logic: 1 USDT = 1000 Points

## Notes

For invite tracking, the bot needs permission to view server invites. If invite logs show unavailable, grant the bot Manage Server or appropriate invite-view permission.

For ROLE shop products, configure `role_id` using `/product_create` or edit the database product row.
