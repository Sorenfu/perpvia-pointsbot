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
- 新增商品「需要钱包地址」开关（`requires_wallet`）与兑换通知：勾选后，用户兑换该商品时若还没有钱包记录，会弹出文本框直接提交 EVM 地址（无需签名，纯自报，适合白名单名额这类场景）；不管商品是否需要钱包，兑换成功后都会私信通知 `OWNER_ID`（商品、兑换人、消耗积分，需要钱包的商品会带上地址与验证状态）。为区分可信度，钱包记录新增"是否签名验证过"标记，`/wallet_holdings`（NFT 持有检测）只信任签名验证过的地址，不采信兑换时自报的地址。详见下方「商城钱包要求」一节。
- 邀请奖励调整：邀请人奖励从 20 改为 50 积分/人（新人的欢迎奖励仍为 10，未变）。
- 新增可选的 `ADMIN_ROLE_ID`：配置后，拥有该身份组的成员也能使用全部 `/admin_*` 指令，不再局限于单一 `OWNER_ID`；`OWNER_ID` 始终拥有最高权限，即使不在该身份组内。留空则只有 `OWNER_ID` 能用管理指令，行为不变。
- `/submit_task` 支持截图证明：新增可选的 `screenshot` 附件参数，可以只提交链接/文字说明、只传截图、或者两者都提交（至少二选一）。审核频道里的消息会直接内嵌显示截图，`/admin_pending_tasks` 兜底列表也会带上截图链接。
- 任务奖励支持区间：`/admin_add_task`、`/admin_edit_task` 新增可选的 `reward_max` 参数，配合 `reward` 组成"150-400"这样的积分区间，用于按内容质量打分的进阶任务，各处展示统一显示为区间形式。
- 每日签到奖励从 10 改为 20 积分/天，新增连续签到奖励：**连续 7 天签到额外 +100 积分**，且每满 7 天循环触发一次（第 7、14、21…天都会再给一次 +100），中断一天会重新从第 1 天算起。`/checkin` 成功后会显示当前连续天数，`/tasks` 里的说明也同步更新。
- 签到"日"的刷新时间点固定为 **UTC+0 的 00:00**（不再依赖服务器系统本地时区，代码里显式按 UTC 计算，避免部署环境时区不一致导致刷新时间跑偏）。已经签到过的用户再次尝试签到，会提示精确到"小时+分钟"的剩余等待时间（例如"Next check-in in **5h 23m**"），不再只是笼统的"明天再来"。
- 任务新增可选的 `repeatable` 参数（默认 `false`）：默认每个用户对同一任务只能完成/提交一次防止刷分，设成 `true` 后可以反复完成/提交、反复拿积分。这个改动同时把"防重复"的判定从数据库唯一约束挪到了应用层（配合 Postgres 咨询锁防止并发重复点击的竞态问题），`/admin_revoke_grant` 现在撤销的是"最近一次"完成记录而不是全部历史。详见「任务系统」一节。
- 新增 `/admin_export_orders`：把全部历史商城兑换记录（订单 ID、兑换人、商品、消耗积分、钱包地址与验证状态、兑换时间）导出成 CSV 文件直接发送，用 Excel/Google Sheets 打开即可统计分析。每笔订单的钱包信息是"兑换那一刻"的快照，不会因为用户之后换绑钱包而变化。

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
ADMIN_ROLE_ID=
DATABASE_URL=
ENVIRONMENT=production
ERROR_WEBHOOK_URL=
```

`ADMIN_ROLE_ID` 为可选项：留空则只有 `OWNER_ID` 能用 `/admin_*` 指令；填一个 Discord 身份组 ID 后，拥有该身份组的成员也能使用全部管理指令（发积分、任务/商品管理、审核任务提交等）。`OWNER_ID` 不受此限制，始终拥有权限。

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

## 商城钱包要求 与 兑换通知

商品可以单独勾选「需要钱包地址」（`requires_wallet`），不勾选的商品行为不变。这个跟上面的 NFT 持有验证是两套独立机制：

- **不需要签名验证**：这里要的只是"知道该发给哪个地址"，不是"证明这个地址真的是他的"，所以走的是比 `/wallet_bind` 更轻的路径——兑换时如果用户还没有任何钱包记录，点击「确认兑换」后会直接弹出一个文本框，输入 EVM 地址（校验格式，不需要签名），提交后立刻完成兑换。
- 如果用户之前已经用 `/wallet_bind` 完整验证过，或者兑换别的商品时报过地址，会直接复用已有记录，不会重复问。
- 钱包记录会标注是「✅ 签名验证过」还是「⚠️ 自报未验证」，`/wallet_status` 和管理员收到的通知里都会显示这个标记。
- **`/wallet_holdings`（NFT 持有检测、发身份组）只认签名验证过的地址**，自报的地址不会被采信去做那个更高权重的判断——避免有人随便填一个不属于自己的地址就骗到持有者身份组。
- 不管商品是否需要钱包，**每次兑换成功都会私信通知 `OWNER_ID`**：商品名称、兑换人、消耗积分；需要钱包的商品会额外带上地址和验证状态。管理员私信关闭时通知会静默失败，不影响兑换本身。
- 每笔订单会把兑换那一刻的钱包地址和验证状态**快照**存进 `orders` 表，跟用户当前绑定的钱包脱钩——就算用户之后解绑、换绑了别的钱包，这笔历史订单查出来的还是当时提交的那个地址，不会被覆盖。
- 创建/编辑商品时加 `requires_wallet:true` 即可开启，例如：
  `/admin_add_product name:Via Genesis Core price:1000 description:... stock:100 requires_wallet:true`

## 任务系统

任务分两种类型，创建/编辑任务时通过 `category` 参数选择：

- **🌱 Basic（基础任务）**：默认类型。用户在 `/tasks` 里看到后，自己执行 `/complete_task task_id:<id>` 立刻拿积分，机器人不做任何核实（荣誉系统）。适合"关注推特""加入 Telegram""设置头像"这类机器人本来就没法自动验证、刷了也无所谓的低门槛任务。
- **⭐ Advanced（进阶任务）**：`/complete_task` 会直接拒绝，提示"需要管理员审核"。适合限时活动、有难度、需要提交凭证（截图/链接）核实的任务。运营在群里/私信收集完凭证并确认无误后，用 `/admin_grant_task task_id:<id> member:<@用户> note:<备注>` 手动把这个任务标记为完成并发放积分；发错了可以用 `/admin_revoke_grant task_id:<id> member:<@用户>` 撤销并扣回积分。

**是否可重复提交**：`/admin_add_task`、`/admin_edit_task` 新增可选的 `repeatable` 参数，**默认 `false`**——每个用户对同一个任务只能完成/提交一次，防止刷分（`/complete_task` 再次尝试会提示"Already Completed"，`/submit_task` 会提示"Already Completed"）。设成 `true` 后，该任务允许同一用户反复完成/提交、反复拿积分，适合"每次分享都给积分"这类没有次数上限的任务。这个开关只影响单个任务，不是全局设置，可以有的任务限一次、有的任务不限。

⚠️ 用到 `repeatable` 之后有个连带影响：`/admin_revoke_grant` 撤销的是**该用户对这个任务最近一次的完成记录**，不是清空他在这个任务上的全部历史——如果一个允许重复的任务某用户已经完成 5 次，`/admin_revoke_grant` 只会撤销第 5 次，前 4 次不受影响。

**限时任务**：`/admin_add_task` 和 `/admin_edit_task` 都有可选的 `starts_at`（开始时间）/ `ends_at`（截止时间）参数，格式固定为 `YYYY-MM-DD HH:MM`（**北京时间**），例如 `2026-07-20 23:59`。不填表示不限时长期开放。开始前/截止后，`/complete_task` 会拒绝领取，`/tasks` 里也会显示对应的状态（⏳ 未开始 / ⏰ 剩余时间 / 🔴 已截止）。`/admin_grant_task` 手动发放不受时间窗口限制，方便活动结束后仍能给已核实的用户补发。

**积分区间**（适合"按内容质量给分"的进阶任务，比如 UGC 创作）：`reward` 参数在 Discord 里是数字类型，只能填一个整数，不能直接填"150-400"这种区间。要表达区间的话，创建/编辑任务时额外填一个可选的 `reward_max` 参数（必须 ≥ `reward`）——`reward` 当作区间下限，`reward_max` 当作上限。设置后 `/tasks`、审核频道消息、`/admin_list_tasks` 等地方都会显示成"+150–400"这种区间形式；批准审核时弹出的打分输入框也会在提示文字里带上这个区间供参考，但不会强制卡在区间内，管理员仍然可以按实际情况填任意数值。区间机制只对「进阶任务」有意义——「基础任务」是自助领取、没有人工打分这一步，就算设了 `reward_max` 也不会生效，用户拿到的永远是 `reward` 这个下限值。

`/tasks` 现在会把基础任务和进阶任务分区展示，进阶任务的提示文案是"需联系管理员审核"而不是指令用法，避免用户误以为可以自助领取。

### 进阶任务审核队列（可选，默认隐藏）

```env
TASK_REVIEW_CHANNEL_ID=
```

- 不配置：进阶任务只能靠「你自己私下收集凭证 + `/admin_grant_task` 手动发放」，`/tasks` 里进阶任务的提示是"完成后联系管理员"，`/submit_task` 命令不会注册（隐藏）。
- 配置了 `TASK_REVIEW_CHANNEL_ID`（填一个 Discord 频道 ID）：
  1. 用户对进阶任务执行 `/submit_task task_id:<id>`，可以填 `proof`（链接/文字说明）、附 `screenshot`（截图），或者两者都提交，至少二选一。机器人会检查任务存在、确实是进阶任务、在开放时间内、没有重复提交，然后把提交信息发到你配置的审核频道，格式是一条 Embed（任务、奖励、提交人、凭证内容、提交时间，截图会直接内嵌显示），带 ✅ 批准 / ❌ 驳回 两个按钮。
  2. 你在频道里直接点按钮：**批准**会自动发放对应积分、把消息更新成"已批准"、私信通知用户；**驳回**会把消息更新成"已驳回"、私信通知用户可以修正后重新提交（同一任务被驳回后可以再次 `/submit_task`，但审核中只能有一条待审提交，重复提交会被拒绝）。
  3. 按钮只有管理员（`OWNER_ID`，或配置了 `ADMIN_ROLE_ID` 的身份组成员）能点，别人点了会提示无权限。按钮是"持久化"的（`discord.ui.DynamicItem`），哪怕机器人重启，几天前发的审核消息上的按钮依然能正常点击生效。
  4. 点「批准」后会弹出一个输入框，预填任务的基础积分（比如 UGC 活动基础分 50），可以直接改成更高或更低的数值再提交——适合"同一个任务，按表现给不同积分"的场景（普通完成给基础分，特别出色的给 500）。实际发放的积分数会被记录下来，跟任务当前配置的基础分脱钩，之后就算你改了任务的基础积分，或者用 `/admin_revoke_grant` 撤销这次发放，扣回的都是当时实际发的那个数，不会算错。
  5. `/admin_grant_task`（不走审核队列，直接手动发放）现在也支持同样的打分：加一个可选的 `amount` 参数覆盖任务基础积分，不填就用任务默认值。
  6. 万一审核消息被刷走找不到了，还有 `/admin_pending_tasks` 命令可以把所有待审核的提交重新列出来（分页展示，含截图链接），照着提示手动 `/admin_grant_task` 也能完成审核。

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
- /submit_task（仅在配置 `TASK_REVIEW_CHANNEL_ID` 后可用，为进阶任务提交凭证等待审核；可提交链接/文字说明、截图，或两者都提交）
- /shop
- /redeem（若商品要求钱包地址且用户还没提交过，确认后会弹窗要求输入 EVM 地址）
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
- /admin_add_task（可选 category / starts_at / ends_at / reward_max / repeatable 参数，见「任务系统」一节）
- /admin_edit_task（同上）
- /admin_grant_task（人工审核后，把某个任务的奖励发给指定用户；可选 amount 参数按表现打分覆盖基础积分）
- /admin_revoke_grant（撤销一次任务发放，扣回对应积分）
- /admin_pending_tasks（列出所有待审核的进阶任务提交，兜底用，正常审核走 `TASK_REVIEW_CHANNEL_ID` 频道里的按钮）
- /admin_remove_task
- /admin_list_tasks（列出全部任务，含已下架，分页展示，含任务类型与时间窗口）
- /admin_add_product（可选 stock 参数，留空为不限量；可选 requires_wallet，勾选后兑换需提交 EVM 地址）
- /admin_edit_product
- /admin_remove_product
- /admin_list_products（列出全部商品，含已下架，分页展示）
- /admin_export_orders（导出全部历史兑换记录为 CSV 文件，含钱包地址快照）
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
