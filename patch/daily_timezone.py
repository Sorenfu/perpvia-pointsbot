# Replace the daily cooldown check

last_time = last['created_at']

if last_time.tzinfo is None:
    last_time = last_time.replace(tzinfo=timezone.utc)

if now - last_time < timedelta(hours=DAILY_COOLDOWN_HOURS):
    remaining = timedelta(hours=DAILY_COOLDOWN_HOURS) - (now-last_time)
    hours = int(remaining.total_seconds() // 3600)
    minutes = int((remaining.total_seconds() % 3600) // 60)
    return False, f'⏳ Daily cooldown active. Try again in {hours}h {minutes}m'
