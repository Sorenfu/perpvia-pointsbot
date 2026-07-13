from datetime import date
from database import db
from modules import points

CHECKIN_REWARD = 10

async def get_active_tasks():
    return await db.fetch("SELECT * FROM tasks WHERE status='ACTIVE' ORDER BY id ASC")

async def create_task(name: str, reward: int, description: str = "", task_type: str = "MANUAL"):
    return await db.fetchrow(
        "INSERT INTO tasks(name, description, reward, task_type, status) VALUES($1,$2,$3,$4,'ACTIVE') RETURNING *",
        name,
        description,
        reward,
        task_type,
    )

async def checkin(user_id: int) -> tuple[bool, str, int]:
    today = date.today()
    exists = await db.fetchrow("SELECT * FROM checkins WHERE user_id=$1 AND checkin_date=$2", user_id, today)
    if exists:
        return False, "Already checked in today.", 0
    await db.execute(
        "INSERT INTO checkins(user_id, checkin_date, reward) VALUES($1, $2, $3)",
        user_id,
        today,
        CHECKIN_REWARD,
    )
    balance = await points.add_points(user_id, CHECKIN_REWARD, "CHECKIN", "Daily check-in")
    return True, "Check-in complete.", balance

async def complete_task(user_id: int, task_id: int) -> tuple[bool, str, int]:
    task = await db.fetchrow("SELECT * FROM tasks WHERE id=$1 AND status='ACTIVE'", task_id)
    if not task:
        return False, "Task not found.", await points.get_balance(user_id)
    if task["task_type"] == "CHECKIN":
        return await checkin(user_id)
    done = await db.fetchrow("SELECT * FROM user_tasks WHERE user_id=$1 AND task_id=$2", user_id, task_id)
    if done and done["completed"]:
        return False, "Task already completed.", await points.get_balance(user_id)
    if done:
        await db.execute("UPDATE user_tasks SET completed=true, completed_at=NOW() WHERE user_id=$1 AND task_id=$2", user_id, task_id)
    else:
        await db.execute("INSERT INTO user_tasks(user_id, task_id, completed, completed_at) VALUES($1,$2,true,NOW())", user_id, task_id)
    balance = await points.add_points(user_id, int(task["reward"]), "TASK_REWARD", task["name"])
    return True, f"Task completed: {task['name']}", balance
