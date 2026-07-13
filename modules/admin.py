from config import OWNER_ID
from database import db

async def is_admin(discord_id: int) -> bool:
    return int(discord_id) == int(OWNER_ID)

async def log_admin(admin_id: int, action: str, details: str = ""):
    await db.execute("INSERT INTO admin_logs(admin_id, action, details) VALUES($1,$2,$3)", admin_id, action, details)
