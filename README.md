# Community OS Lite Beta 1.0.12

Railway-ready Discord积分商城系统。

## 功能

- `/profile` 用户资料，自动注册用户
- `/points` 查询积分
- `/tasks` 查看任务
- `/checkin` 每日签到，奖励10积分
- `/complete_task` 完成任务并获得积分
- `/shop` 查看商城商品
- `/redeem` 使用积分兑换商品并发放 Discord Role
- `/orders` 查看订单
- `/invite` 创建邀请链接
- `/referrals` 查看邀请统计
- `/admin_add_points` 管理员发积分
- `/admin_add_task` 管理员创建任务
- `/admin_add_product` 管理员创建商品
- `/admin_stats` 管理员查看数据

## 邀请规则

- 邀请人：+20 Points
- 新用户：+10 Points
- 触发条件：新用户通过邀请链接加入服务器后，发送至少一条长度不少于5字符的消息。

## Railway 部署

1. 创建 Railway Worker 服务。
2. 添加 PostgreSQL 服务。
3. 在 Worker 环境变量中配置：

```env
DISCORD_TOKEN=
OWNER_ID=
DATABASE_URL=
ENVIRONMENT=production
```

4. Start Command:

```bash
python bot.py
```

## Discord Bot 权限

必须打开：

- Server Members Intent
- Message Content Intent

Bot 需要权限：

- Use Application Commands
- Send Messages
- Read Message History
- Create Invite
- Manage Roles（商城兑换发Role需要）

Bot 的角色必须高于需要发放的角色。

## 创建商品

使用：

```text
/admin_add_product name:VIP Member price:1000 role_id:你的RoleID
```

## 创建任务

```text
/admin_add_task name:AMA reward:200 description:Join AMA
```

## 注意

这是 Lite 版本，目标是先跑通：任务/签到 → 积分 → 商城兑换 → Role权益。后续可以在此基础上继续优化。
