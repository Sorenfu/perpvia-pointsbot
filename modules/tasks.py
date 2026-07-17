from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

import asyncpg

from config import TASK_REVIEW_CHANNEL_ID
from modules.points import add_points

DAILY_CHECKIN_REWARD = 20
CHECKIN_STREAK_LENGTH = 7
CHECKIN_STREAK_BONUS = 100
CHECKIN_RESET_HOUR_UTC = 0  # the check-in "day" rolls over at 00:00 UTC


def current_checkin_period(now: datetime | None = None) -> date:
    """The check-in 'day' rolls over at 00:00 UTC, so shift back by that offset before taking the date."""
    now = now or datetime.now(timezone.utc)
    return (now - timedelta(hours=CHECKIN_RESET_HOUR_UTC)).date()


def next_checkin_reset(now: datetime | None = None) -> datetime:
    now = now or datetime.now(timezone.utc)
    reset_today = now.replace(hour=CHECKIN_RESET_HOUR_UTC, minute=0, second=0, microsecond=0)
    return reset_today if now < reset_today else reset_today + timedelta(days=1)


def time_until_next_checkin_text(now: datetime | None = None) -> str:
    now = now or datetime.now(timezone.utc)
    remaining = next_checkin_reset(now) - now
    total_minutes = max(0, int(remaining.total_seconds() // 60))
    hours, minutes = divmod(total_minutes, 60)
    if hours and minutes:
        return f"{hours}h {minutes}m"
    if hours:
        return f"{hours}h"
    return f"{minutes}m"

CATEGORY_BASIC = "BASIC"
CATEGORY_ADVANCED = "ADVANCED"
TASK_CATEGORIES = (CATEGORY_BASIC, CATEGORY_ADVANCED)

CATEGORY_LABELS = {
    CATEGORY_BASIC: "🌱 Basic",
    CATEGORY_ADVANCED: "⭐ Advanced (admin-reviewed)",
}

BEIJING_TZ = timezone(timedelta(hours=8), name="Asia/Shanghai")
DATETIME_INPUT_FORMAT = "%Y-%m-%d %H:%M"


async def _lock_user_task(conn, discord_id: int, task_id: int) -> None:
    """Serializes concurrent completion attempts for the same (discord_id, task_id) pair.

    Must be called inside a transaction — the lock is held until commit/rollback.
    Needed because user_tasks no longer has a DB-level uniqueness constraint
    (repeatable tasks require multiple rows per user), so "already completed"
    is checked at the application level and must be raced-proofed manually.
    """
    await conn.execute("SELECT pg_advisory_xact_lock(hashtext($1))", f"user_task:{discord_id}:{task_id}")


def category_label(category: str) -> str:
    return CATEGORY_LABELS.get(category, category)


def repeatable_label(repeatable: bool) -> str:
    return "🔁 Repeatable" if repeatable else "1x per user"


def parse_task_datetime(value: str | None) -> datetime | None:
    """Parses a 'YYYY-MM-DD HH:MM' string given in Beijing time into a naive UTC datetime for storage."""
    if not value or not value.strip():
        return None
    try:
        local_dt = datetime.strptime(value.strip(), DATETIME_INPUT_FORMAT).replace(tzinfo=BEIJING_TZ)
    except ValueError:
        raise ValueError(f"Invalid datetime '{value}'. Expected format: YYYY-MM-DD HH:MM (Beijing time), e.g. 2026-07-20 23:59")
    return local_dt.astimezone(timezone.utc).replace(tzinfo=None)


def format_task_datetime(value: datetime | None) -> str | None:
    if value is None:
        return None
    return value.replace(tzinfo=timezone.utc).astimezone(BEIJING_TZ).strftime(DATETIME_INPUT_FORMAT)


def is_task_open(task) -> bool:
    now = datetime.now(timezone.utc)
    starts_at = task["starts_at"]
    ends_at = task["ends_at"]
    if starts_at and now < starts_at.replace(tzinfo=timezone.utc):
        return False
    if ends_at and now > ends_at.replace(tzinfo=timezone.utc):
        return False
    return True


def reward_text(reward: int, reward_max: int | None) -> str:
    if reward_max is not None and int(reward_max) > int(reward):
        return f"+{reward}–{reward_max}"
    return f"+{reward}"


def task_window_text(task) -> str:
    now = datetime.now(timezone.utc)
    starts_at = task["starts_at"]
    ends_at = task["ends_at"]

    if starts_at and now < starts_at.replace(tzinfo=timezone.utc):
        return f"⏳ Starts {format_task_datetime(starts_at)} (Beijing time)"
    if ends_at and now > ends_at.replace(tzinfo=timezone.utc):
        return f"🔴 Ended {format_task_datetime(ends_at)} (Beijing time)"
    if ends_at:
        return f"⏰ Ends {format_task_datetime(ends_at)} (Beijing time)"
    return "🟢 Open-ended"


async def list_active_tasks(db):
    return await db.fetch("SELECT * FROM tasks WHERE status='ACTIVE' ORDER BY id ASC")


async def list_all_tasks(db):
    return await db.fetch("SELECT * FROM tasks ORDER BY id ASC")


async def create_task(
    db,
    name: str,
    reward: int,
    description: str | None = None,
    category: str = CATEGORY_BASIC,
    starts_at: datetime | None = None,
    ends_at: datetime | None = None,
    reward_max: int | None = None,
    repeatable: bool = False,
):
    return await db.fetchrow(
        '''
        INSERT INTO tasks (name, reward, description, category, starts_at, ends_at, reward_max, repeatable)
        VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
        RETURNING *
        ''',
        name,
        int(reward),
        description,
        category,
        starts_at,
        ends_at,
        int(reward_max) if reward_max is not None else None,
        bool(repeatable),
    )


async def edit_task(
    db,
    task_id: int,
    name: str,
    reward: int,
    description: str | None = None,
    category: str = CATEGORY_BASIC,
    starts_at: datetime | None = None,
    ends_at: datetime | None = None,
    reward_max: int | None = None,
    repeatable: bool = False,
):
    return await db.fetchrow(
        '''
        UPDATE tasks
        SET name=$2, reward=$3, description=$4, category=$5, starts_at=$6, ends_at=$7, reward_max=$8, repeatable=$9
        WHERE id=$1 AND status='ACTIVE'
        RETURNING *
        ''',
        int(task_id),
        name,
        int(reward),
        description,
        category,
        starts_at,
        ends_at,
        int(reward_max) if reward_max is not None else None,
        bool(repeatable),
    )


async def remove_task(db, task_id: int):
    return await db.fetchrow(
        "UPDATE tasks SET status='INACTIVE' WHERE id=$1 AND status='ACTIVE' RETURNING *",
        int(task_id),
    )


async def get_checkin_streak(db, discord_id: int) -> int:
    """Counts consecutive check-in periods ending now (breaks on the first gap)."""
    rows = await db.fetch(
        "SELECT checkin_date FROM checkins WHERE discord_id=$1 ORDER BY checkin_date DESC",
        int(discord_id),
    )
    streak = 0
    expected = current_checkin_period()
    for row in rows:
        if row["checkin_date"] == expected:
            streak += 1
            expected -= timedelta(days=1)
        else:
            break
    return streak


async def daily_checkin(db, discord_id: int):
    """Returns None if already checked in this period, otherwise {'streak': int, 'bonus_awarded': bool}."""
    today = current_checkin_period()
    inserted = await db.fetchrow(
        '''
        INSERT INTO checkins (discord_id, checkin_date)
        VALUES ($1, $2)
        ON CONFLICT (discord_id, checkin_date)
        DO NOTHING
        RETURNING id
        ''',
        int(discord_id),
        today,
    )
    if not inserted:
        return None

    await add_points(db, discord_id, DAILY_CHECKIN_REWARD, "CHECKIN", "Daily check-in")

    streak = await get_checkin_streak(db, discord_id)
    bonus_awarded = streak > 0 and streak % CHECKIN_STREAK_LENGTH == 0
    if bonus_awarded:
        await add_points(
            db, discord_id, CHECKIN_STREAK_BONUS, "CHECKIN_STREAK", f"{CHECKIN_STREAK_LENGTH}-day check-in streak bonus"
        )

    return {"streak": streak, "bonus_awarded": bonus_awarded}


async def complete_task(db, discord_id: int, task_id: int):
    """Self-serve task completion. Only allowed for open, BASIC-category tasks."""
    task = await db.fetchrow("SELECT * FROM tasks WHERE id=$1 AND status='ACTIVE'", int(task_id))
    if not task:
        return None, "TASK_NOT_FOUND"

    if task["category"] != CATEGORY_BASIC:
        return task, "NOT_SELF_SERVE"

    if not is_task_open(task):
        now = datetime.now(timezone.utc)
        if task["starts_at"] and now < task["starts_at"].replace(tzinfo=timezone.utc):
            return task, "NOT_STARTED"
        return task, "EXPIRED"

    async with db.transaction() as conn:
        await _lock_user_task(conn, discord_id, task_id)

        if not task["repeatable"]:
            existing = await conn.fetchrow(
                "SELECT id FROM user_tasks WHERE discord_id=$1 AND task_id=$2", int(discord_id), int(task_id)
            )
            if existing:
                return task, "ALREADY_DONE"

        await conn.execute(
            "INSERT INTO user_tasks (discord_id, task_id, awarded_points) VALUES ($1, $2, $3)",
            int(discord_id),
            int(task_id),
            int(task["reward"]),
        )
        await add_points(conn, discord_id, int(task["reward"]), "TASK", f"Completed task: {task['name']}")

    return task, "OK"


async def grant_task(db, admin_discord_id: int, discord_id: int, task_id: int, note: str | None = None, amount: int | None = None):
    """Admin-side manual grant, used after reviewing proof for ADVANCED (or any) tasks.

    `amount` overrides the task's base reward, for performance-based scoring
    (e.g. a UGC task has a base reward but strong submissions get paid more).
    """
    task = await db.fetchrow("SELECT * FROM tasks WHERE id=$1 AND status='ACTIVE'", int(task_id))
    if not task:
        return None, "TASK_NOT_FOUND"

    award_amount = int(amount) if amount is not None else int(task["reward"])

    async with db.transaction() as conn:
        await _lock_user_task(conn, discord_id, task_id)

        if not task["repeatable"]:
            existing = await conn.fetchrow(
                "SELECT id FROM user_tasks WHERE discord_id=$1 AND task_id=$2", int(discord_id), int(task_id)
            )
            if existing:
                return task, "ALREADY_DONE"

        await conn.execute(
            '''
            INSERT INTO user_tasks (discord_id, task_id, granted_by, note, awarded_points)
            VALUES ($1, $2, $3, $4, $5)
            ''',
            int(discord_id),
            int(task_id),
            int(admin_discord_id),
            note,
            award_amount,
        )
        await add_points(
            conn, discord_id, award_amount, "TASK_GRANT", f"Granted task: {task['name']} (awarded {award_amount}, by admin)"
        )

    return task, "OK"


async def revoke_task_grant(db, discord_id: int, task_id: int):
    """Undo the most recent completion of a task (self-serve or granted) and claw back exactly the
    points that were paid out for it — not the task's current base reward, which may have changed since.

    Repeatable tasks can have several completions on file; this only undoes the latest one.
    """
    async with db.transaction() as conn:
        row = await conn.fetchrow(
            '''
            DELETE FROM user_tasks
            WHERE id = (
                SELECT id FROM user_tasks
                WHERE discord_id=$1 AND task_id=$2
                ORDER BY completed_at DESC, id DESC
                LIMIT 1
            )
            RETURNING id, awarded_points
            ''',
            int(discord_id),
            int(task_id),
        )
        if not row:
            return None, "NOT_FOUND"

        task = await conn.fetchrow("SELECT * FROM tasks WHERE id=$1", int(task_id))
        claw_back = row["awarded_points"]
        if claw_back is None and task:
            claw_back = int(task["reward"])
        if claw_back:
            task_name = task["name"] if task else f"#{task_id}"
            await add_points(conn, discord_id, -int(claw_back), "TASK_REVOKED", f"Revoked task: {task_name}")
    return task, "OK"


def is_review_enabled() -> bool:
    return bool(TASK_REVIEW_CHANNEL_ID)


async def create_submission(db, discord_id: int, task_id: int, proof: str | None, proof_image_url: str | None = None):
    """User-side submission for an ADVANCED task, queued for admin review.

    Proof can be a text/link description, a screenshot (proof_image_url), or both.
    """
    task = await db.fetchrow("SELECT * FROM tasks WHERE id=$1 AND status='ACTIVE'", int(task_id))
    if not task:
        return task, None, "TASK_NOT_FOUND"

    if task["category"] != CATEGORY_ADVANCED:
        return task, None, "NOT_ADVANCED"

    if not is_task_open(task):
        now = datetime.now(timezone.utc)
        if task["starts_at"] and now < task["starts_at"].replace(tzinfo=timezone.utc):
            return task, None, "NOT_STARTED"
        return task, None, "EXPIRED"

    if not task["repeatable"]:
        already_done = await db.fetchrow(
            "SELECT id FROM user_tasks WHERE discord_id=$1 AND task_id=$2", int(discord_id), int(task_id)
        )
        if already_done:
            return task, None, "ALREADY_DONE"

    try:
        submission = await db.fetchrow(
            '''
            INSERT INTO task_submissions (discord_id, task_id, proof, proof_image_url)
            VALUES ($1, $2, $3, $4)
            RETURNING *
            ''',
            int(discord_id),
            int(task_id),
            proof,
            proof_image_url,
        )
    except asyncpg.UniqueViolationError:
        return task, None, "ALREADY_PENDING"

    return task, submission, "OK"


async def set_submission_message(db, submission_id: int, message_id: int) -> None:
    await db.execute(
        "UPDATE task_submissions SET message_id=$2 WHERE id=$1", int(submission_id), int(message_id)
    )


async def get_submission_with_task(db, submission_id: int):
    return await db.fetchrow(
        '''
        SELECT s.*, t.name AS task_name, t.reward AS task_reward, t.reward_max AS task_reward_max
        FROM task_submissions s
        JOIN tasks t ON t.id = s.task_id
        WHERE s.id=$1
        ''',
        int(submission_id),
    )


async def list_pending_submissions(db):
    return await db.fetch(
        '''
        SELECT s.*, t.name AS task_name, t.reward AS task_reward, t.reward_max AS task_reward_max
        FROM task_submissions s
        JOIN tasks t ON t.id = s.task_id
        WHERE s.status='PENDING'
        ORDER BY s.id ASC
        '''
    )


async def approve_submission(db, submission_id: int, reviewer_discord_id: int, amount: int | None = None):
    """Approves a pending submission. `amount` overrides the task's base reward for
    performance-based scoring (e.g. a UGC task pays more for stronger entries)."""
    async with db.transaction() as conn:
        submission = await conn.fetchrow(
            "SELECT * FROM task_submissions WHERE id=$1 AND status='PENDING' FOR UPDATE",
            int(submission_id),
        )
        if not submission:
            return None, "NOT_PENDING"

        task = await conn.fetchrow("SELECT * FROM tasks WHERE id=$1", int(submission["task_id"]))
        award_amount = int(amount) if amount is not None else (int(task["reward"]) if task else 0)

        await _lock_user_task(conn, submission["discord_id"], submission["task_id"])

        already_granted = False
        if task and not task["repeatable"]:
            existing = await conn.fetchrow(
                "SELECT id FROM user_tasks WHERE discord_id=$1 AND task_id=$2",
                int(submission["discord_id"]),
                int(submission["task_id"]),
            )
            already_granted = existing is not None

        if not already_granted:
            await conn.execute(
                '''
                INSERT INTO user_tasks (discord_id, task_id, granted_by, note, awarded_points)
                VALUES ($1, $2, $3, $4, $5)
                ''',
                int(submission["discord_id"]),
                int(submission["task_id"]),
                int(reviewer_discord_id),
                submission["proof"],
                award_amount,
            )
            if task:
                await add_points(
                    conn,
                    submission["discord_id"],
                    award_amount,
                    "TASK_GRANT",
                    f"Approved submission: {task['name']} (awarded {award_amount})",
                )

        await conn.execute(
            '''
            UPDATE task_submissions
            SET status='APPROVED', reviewed_by=$2, reviewed_at=NOW(), awarded_points=$3
            WHERE id=$1
            ''',
            int(submission_id),
            int(reviewer_discord_id),
            award_amount,
        )

    result = await get_submission_with_task(db, submission_id)
    return result, "OK"


async def reject_submission(db, submission_id: int, reviewer_discord_id: int, note: str | None = None):
    row = await db.fetchrow(
        '''
        UPDATE task_submissions
        SET status='REJECTED', reviewed_by=$2, review_note=$3, reviewed_at=NOW()
        WHERE id=$1 AND status='PENDING'
        RETURNING id
        ''',
        int(submission_id),
        int(reviewer_discord_id),
        note,
    )
    if not row:
        return None, "NOT_PENDING"

    result = await get_submission_with_task(db, submission_id)
    return result, "OK"
