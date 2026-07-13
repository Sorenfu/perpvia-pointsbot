# Community OS Lite Beta 1.0.12 - Fixed Source

这是修复版完整源码包。

## 本次修复

Railway 日志中的核心报错：

```text
asyncpg.exceptions.UndefinedColumnError: column "id" referenced in foreign key constraint does not exist
```

原因是旧版 SQL 里有表引用 `users(id)`，但 Railway 当前数据库中的 `users` 表可能没有 `id` 字段。

本版本已修复：

- 不再使用 `users(id)` 外键。
- 统一以 `discord_id` 作为用户主键/业务关联键。
- `init.sql` 增加兼容性 ALTER。
- 避免旧数据库残留结构导致启动失败。

## Railway 环境变量

```env
DISCORD_TOKEN=
OWNER_ID=
DATABASE_URL=
ENVIRONMENT=production
```

## 启动命令

```bash
python bot.py
```

## Discord Developer Portal 必须开启

- Server Members Intent
- Message Content Intent

## Bot 权限建议

- Send Messages
- Use Slash Commands
- Create Invite
- Manage Roles
- Read Message History
- View Channels

## 命令

用户：

- /ping
- /profile
- /points
- /tasks
- /checkin
- /complete_task
- /shop
- /redeem
- /orders
- /invite
- /referrals

管理员：

- /admin_add_points
- /admin_add_task
- /admin_add_product
- /admin_stats

## 如果仍然启动失败

如果 Railway PostgreSQL 已经有旧的半初始化表，最干净的处理方式是：

1. Railway Postgres 打开 Query
2. 删除旧表后重新部署

```sql
DROP TABLE IF EXISTS admin_logs;
DROP TABLE IF EXISTS referrals;
DROP TABLE IF EXISTS invite_codes;
DROP TABLE IF EXISTS orders;
DROP TABLE IF EXISTS products;
DROP TABLE IF EXISTS checkins;
DROP TABLE IF EXISTS user_tasks;
DROP TABLE IF EXISTS tasks;
DROP TABLE IF EXISTS points;
DROP TABLE IF EXISTS users;
```

然后重启 Worker。
