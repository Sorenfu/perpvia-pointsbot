import os
from dotenv import load_dotenv

load_dotenv()

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN", "").strip()
DATABASE_URL = os.getenv("DATABASE_URL", "").strip()
OWNER_ID = int(os.getenv("OWNER_ID", "0") or "0")
ENVIRONMENT = os.getenv("ENVIRONMENT", "production")

if not DISCORD_TOKEN:
    raise RuntimeError("Missing DISCORD_TOKEN environment variable")

if not DATABASE_URL:
    raise RuntimeError("Missing DATABASE_URL environment variable")

if OWNER_ID == 0:
    raise RuntimeError("Missing OWNER_ID environment variable")
