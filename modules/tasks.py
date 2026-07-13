from __future__ import annotations

from datetime import date
from modules.points import add_points


DAILY_CHECKIN_REWARD = 10


async def list_active_tasks(db):
    return await db.fetch("SELECT * FROM tasks WHERE status='ACTIVE' ORDER BY id ASC")


async def create_task(db, name: str, reward: int, description: str | None = None):
    return await db.fetchrow(
        "INSERT INTO tasks (name, reward, description) VALUES ($1, $2, $3) RETURNING *",
        name,
        int(reward),
        description,
    )


async def daily_checkin(db, discord_id: int):
    today = date.today()
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
        return False
    await add_points(db, discord_id, DAILY_CHECKIN_REWARD, "CHECKIN", "Daily check-in")
    return True


async def complete_task(db, discord_id: int, task_id: int):
    task = await db.fetchrow("SELECT * FROM tasks WHERE id=$1 AND status='ACTIVE'", int(task_id))
    if not task:
        return None, "TASK_NOT_FOUND"

    inserted = await db.fetchrow(
        '''
        INSERT INTO user_tasks (discord_id, task_id)
        VALUES ($1, $2)
        ON CONFLICT (discord_id, task_id)
        DO NOTHING
        RETURNING id
        ''',
        int(discord_id),
        int(task_id),
    )
    if not inserted:
        return task, "ALREADY_DONE"

    await add_points(db, discord_id, int(task["reward"]), "TASK", f"Completed task: {task['name']}")
    return task, "OK"
