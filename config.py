import os
from dotenv import load_dotenv

load_dotenv()

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN", "")
OWNER_ID = int(os.getenv("OWNER_ID", "0") or 0)
DATABASE_URL = os.getenv("DATABASE_URL", "")
ENVIRONMENT = os.getenv("ENVIRONMENT", "production")

if not DISCORD_TOKEN:
    print("WARNING: DISCORD_TOKEN is empty")
if not DATABASE_URL:
    print("WARNING: DATABASE_URL is empty")
