# Community OS Lite Beta 1.0.12 - Fixed Source

这是修复版完整源码包。

## 功能迭代（本次新增）

- 商品新增 `stock` 库存字段，库存为空表示不限量，售罄后无法兑换。
- 每个用户对同一个商品/角色只能兑换一次（不影响兑换其他不同商品）。
- 新增管理员命令：`/admin_edit_product`、`/admin_remove_product`、`/admin_edit_task`、`/admin_remove_task`，支持编辑与下架（软删除，历史订单不受影响）。
- 所有面向用户的消息统一改为 Embed 展示，任务/商城板块增加图标与结构化排版。
- 新增 `/leaderboard` 排行榜命令，可选 总榜 / 积分榜 / 邀请榜。
- 新增全局 Slash 命令错误处理器，命令出错时给用户统一的友好提示，不再直接失败无响应。
- 新增可选的 Discord Webhook 报警：配置 `ERROR_WEBHOOK_URL` 后，命令异常、消息处理异常、slash 同步失败等都会自动推送到指定频道。
- 新增"每日发言"被动任务：用户在服务器发言即可获得积分，带每条消息冷却时间与每日封顶（默认：每条 +1 积分，冷却 60 秒，每日上限 20 积分），可在 `/tasks` 中查看今日进度。数值定义在 [modules/activity.py](modules/activity.py) 顶部，可按需调整。
- 新增 `/points_history` 积分明细命令，展示最近 10 笔积分变动（类型、原因、时间）。
- `/redeem` 兑换商品前新增二次确认按钮（确认/取消），展示商品信息、当前余额与兑换后余额，避免误触；实际扣分仍在确认后于数据库事务中二次校验库存与余额。
- `/shop`、`/tasks`、`/orders`、`/leaderboard`（points/invites 单榜）列表过长时自动分页，翻页按钮仅发起者可操作，超时自动禁用。
- 新增管理员命令 `/admin_list_tasks`、`/admin_list_products`，列出全部任务/商品（含已下架），分页展示，方便管理员回溯已下架内容。
- `/redeem` 加每用户 5 秒冷却，`/invite` 加每用户 15 秒冷却，防止被脚本刷指令。冷却触发时会提示剩余等待时间。
- `/admin_stats` 新增指标：今日活跃用户数、近 7 日活跃用户数（基于每日发言记录）、商城累计消耗积分、待发放邀请奖励数。
- 新增钱包持有验证（EVM/Base 链）：`/wallet_bind`、`/wallet_confirm`、`/wallet_status`、`/wallet_unbind` 用签名校验钱包所有权（纯本地密码学验证，不依赖任何第三方付费服务），随时可用。`/wallet_holdings`（查询 NFT 持有数量并自动发放持有者身份组）依赖 `NFT_CONTRACT_ADDRESS` 与 `NFT_RPC_URL` 两个环境变量，**留空时该命令不会注册，等于隐藏**；配置好合约地址和 RPC 节点后重启即可直接生效，无需改代码。详见下方「NFT 持有验证」一节。
- 任务系统升级，区分「基础任务」与「进阶任务」，并支持限时任务，详见下方「任务系统」一节。
- 新增进阶任务审核队列：配置 `TASK_REVIEW_CHANNEL_ID` 后，用户可用 `/submit_task` 提交凭证，机器人自动把提交信息发到指定频道，附「批准/驳回」按钮，管理员点按钮即可审核并自动发放/拒绝，同时私信通知用户结果。留空则该命令隐藏，行为回退成"手动联系管理员"。详见下方「任务系统」一节。
- 审核通过时支持按表现打分：批准按钮会弹出输入框，预填任务基础积分，可改成更高/更低的数值（如基础 50、优秀内容给 500）；`/admin_grant_task` 也加了同样的可选 `amount` 参数。实际发放数额独立记录，`/admin_revoke_grant` 撤销时精确扣回当时发的数额，不受任务基础积分后续变动影响。

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
ERROR_WEBHOOK_URL=
```

`ERROR_WEBHOOK_URL` 为可选项：留空则不发送报警；填写一个 Discord 频道的 Webhook URL 后，机器人运行中出现的未捕获异常会自动推送到该频道。

## NFT 持有验证（可选，默认隐藏）

```env
NFT_CONTRACT_ADDRESS=
NFT_RPC_URL=
NFT_HOLDER_ROLE_ID=
```

- `/wallet_bind`、`/wallet_confirm`、`/wallet_status`、`/wallet_unbind` 四个钱包绑定命令**始终可用**，不需要以上任何配置——验证的是"这个钱包地址确实是这个人的"，靠的是让用户对一段包含随机 nonce 的消息签名，机器人本地用 `eth_account` 校验签名来源地址，全程不发起任何网络请求，零成本、不依赖第三方。可以现在就让社区成员提前绑定钱包。
- `/wallet_holdings`（查询钱包在指定合约下的 NFT 持有数量，并按 `NFT_HOLDER_ROLE_ID` 自动发放身份组）**只有在 `NFT_CONTRACT_ADDRESS` 和 `NFT_RPC_URL` 都配置后才会注册为 Slash 命令**，两者留空时这个命令完全不存在，等于功能隐藏，不会出现在指令列表里，也不会误导用户使用一个查不到东西的命令。
- `NFT_CONTRACT_ADDRESS`：Base 链（或其他 EVM 链）上的 NFT 合约地址（`0x...`）。
- `NFT_RPC_URL`：一个可用的 EVM JSON-RPC 节点地址（例如 Base 官方公共节点、或 Alchemy/Infura 等付费节点的 URL）。免费公共节点可先用于测试，正式上线建议换成有 SLA 保障的付费节点，只需替换这一个环境变量，不用改代码。
- `NFT_HOLDER_ROLE_ID`：持有者身份组的 Discord Role ID，可选；不填则只查询持有数量、不自动发放身份组。

## 任务系统

任务分两种类型，创建/编辑任务时通过 `category` 参数选择：

- **🌱 Basic（基础任务）**：默认类型。用户在 `/tasks` 里看到后，自己执行 `/complete_task task_id:<id>` 立刻拿积分，机器人不做任何核实（荣誉系统）。适合"关注推特""加入 Telegram""设置头像"这类机器人本来就没法自动验证、刷了也无所谓的低门槛任务。
- **⭐ Advanced（进阶任务）**：`/complete_task` 会直接拒绝，提示"需要管理员审核"。适合限时活动、有难度、需要提交凭证（截图/链接）核实的任务。运营在群里/私信收集完凭证并确认无误后，用 `/admin_grant_task task_id:<id> member:<@用户> note:<备注>` 手动把这个任务标记为完成并发放积分；发错了可以用 `/admin_revoke_grant task_id:<id> member:<@用户>` 撤销并扣回积分。

**限时任务**：`/admin_add_task` 和 `/admin_edit_task` 都有可选的 `starts_at`（开始时间）/ `ends_at`（截止时间）参数，格式固定为 `YYYY-MM-DD HH:MM`（**北京时间**），例如 `2026-07-20 23:59`。不填表示不限时长期开放。开始前/截止后，`/complete_task` 会拒绝领取，`/tasks` 里也会显示对应的状态（⏳ 未开始 / ⏰ 剩余时间 / 🔴 已截止）。`/admin_grant_task` 手动发放不受时间窗口限制，方便活动结束后仍能给已核实的用户补发。

`/tasks` 现在会把基础任务和进阶任务分区展示，进阶任务的提示文案是"需联系管理员审核"而不是指令用法，避免用户误以为可以自助领取。

### 进阶任务审核队列（可选，默认隐藏）

```env
TASK_REVIEW_CHANNEL_ID=
```

- 不配置：进阶任务只能靠「你自己私下收集凭证 + `/admin_grant_task` 手动发放」，`/tasks` 里进阶任务的提示是"完成后联系管理员"，`/submit_task` 命令不会注册（隐藏）。
- 配置了 `TASK_REVIEW_CHANNEL_ID`（填一个 Discord 频道 ID）：
  1. 用户对进阶任务执行 `/submit_task task_id:<id> proof:<截图链接/说明文字>`，机器人会检查任务存在、确实是进阶任务、在开放时间内、没有重复提交，然后把提交信息发到你配置的审核频道，格式是一条 Embed（任务、奖励、提交人、凭证内容、提交时间），带 ✅ 批准 / ❌ 驳回 两个按钮。
  2. 你在频道里直接点按钮：**批准**会自动发放对应积分、把消息更新成"已批准"、私信通知用户；**驳回**会把消息更新成"已驳回"、私信通知用户可以修正后重新提交（同一任务被驳回后可以再次 `/submit_task`，但审核中只能有一条待审提交，重复提交会被拒绝）。
  3. 按钮只有管理员（`OWNER_ID`）能点，别人点了会提示无权限。按钮是"持久化"的（`discord.ui.DynamicItem`），哪怕机器人重启，几天前发的审核消息上的按钮依然能正常点击生效。
  4. 点「批准」后会弹出一个输入框，预填任务的基础积分（比如 UGC 活动基础分 50），可以直接改成更高或更低的数值再提交——适合"同一个任务，按表现给不同积分"的场景（普通完成给基础分，特别出色的给 500）。实际发放的积分数会被记录下来，跟任务当前配置的基础分脱钩，之后就算你改了任务的基础积分，或者用 `/admin_revoke_grant` 撤销这次发放，扣回的都是当时实际发的那个数，不会算错。
  5. `/admin_grant_task`（不走审核队列，直接手动发放）现在也支持同样的打分：加一个可选的 `amount` 参数覆盖任务基础积分，不填就用任务默认值。
  4. 万一审核消息被刷走找不到了，还有 `/admin_pending_tasks` 命令可以把所有待审核的提交重新列出来（分页展示），照着提示手动 `/admin_grant_task` 也能完成审核。

## 本地开发

复制 `.env.example` 为 `.env` 并填入对应的值，`config.py` 会通过 `python-dotenv` 自动加载：

```bash
cp .env.example .env
```

`.env` 已在 `.gitignore` 中排除，不会被提交到仓库。

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
- /points_history
- /tasks
- /checkin
- /complete_task
- /submit_task（仅在配置 `TASK_REVIEW_CHANNEL_ID` 后可用，为进阶任务提交凭证等待审核）
- /shop
- /redeem
- /orders
- /invite
- /referrals
- /leaderboard（可选 board 参数：总榜 overall / 积分榜 points / 邀请榜 invites）
- /wallet_bind（提交钱包地址，开始签名验证）
- /wallet_confirm（提交签名，完成钱包绑定）
- /wallet_status（查看已绑定的钱包）
- /wallet_unbind（解绑钱包）
- /wallet_holdings（仅在配置 `NFT_CONTRACT_ADDRESS` + `NFT_RPC_URL` 后可用，查询 NFT 持有数量并同步身份组）

管理员：

- /admin_add_points
- /admin_add_task（可选 category / starts_at / ends_at 参数，见「任务系统」一节）
- /admin_edit_task（同上）
- /admin_grant_task（人工审核后，把某个任务的奖励发给指定用户；可选 amount 参数按表现打分覆盖基础积分）
- /admin_revoke_grant（撤销一次任务发放，扣回对应积分）
- /admin_pending_tasks（列出所有待审核的进阶任务提交，兜底用，正常审核走 `TASK_REVIEW_CHANNEL_ID` 频道里的按钮）
- /admin_remove_task
- /admin_list_tasks（列出全部任务，含已下架，分页展示，含任务类型与时间窗口）
- /admin_add_product（可选 stock 参数，留空为不限量）
- /admin_edit_product
- /admin_remove_product
- /admin_list_products（列出全部商品，含已下架，分页展示）
- /admin_stats

## 如果仍然启动失败

如果 Railway PostgreSQL 已经有旧的半初始化表，最干净的处理方式是：

1. Railway Postgres 打开 Query
2. 删除旧表后重新部署

```sql
DROP TABLE IF EXISTS admin_logs;
DROP TABLE IF EXISTS task_submissions;
DROP TABLE IF EXISTS wallet_nonces;
DROP TABLE IF EXISTS wallet_bindings;
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
