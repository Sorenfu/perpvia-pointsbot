from datetime import datetime, timezone, timedelta

async def check_daily_cooldown(last_time, cooldown_hours=12):
    now = datetime.now(timezone.utc)

    if last_time is None:
        return True, None

    # PostgreSQL TIMESTAMP compatibility
    if last_time.tzinfo is None:
        last_time = last_time.replace(tzinfo=timezone.utc)

    elapsed = now - last_time
    cooldown = timedelta(hours=cooldown_hours)

    if elapsed < cooldown:
        remain = cooldown - elapsed
        hours = int(remain.total_seconds() // 3600)
        minutes = int((remain.total_seconds() % 3600) // 60)
        return False, f'⏳ Daily cooldown active. Try again in {hours}h {minutes}m'

    return True, None
