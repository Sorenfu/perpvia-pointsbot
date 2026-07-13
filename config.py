import os
from dotenv import load_dotenv

load_dotenv()

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN", "").strip()
DATABASE_URL = os.getenv("DATABASE_URL", "").strip()
_owner_id_raw = os.getenv("OWNER_ID", "").strip()
ENVIRONMENT = os.getenv("ENVIRONMENT", "production")

if not DISCORD_TOKEN:
    raise RuntimeError("Missing DISCORD_TOKEN environment variable")

if not DATABASE_URL:
    raise RuntimeError("Missing DATABASE_URL environment variable")

if not _owner_id_raw:
    raise RuntimeError(
        "Missing OWNER_ID environment variable. Set it in Railway -> Variables "
        "to your own Discord user ID (right-click your name in Discord with "
        "Developer Mode on -> Copy User ID)."
    )

try:
    OWNER_ID = int(_owner_id_raw)
except ValueError:
    raise RuntimeError(
        f"OWNER_ID must be a numeric Discord user ID, got: {_owner_id_raw!r}"
    ) from None

if OWNER_ID == 0:
    raise RuntimeError("OWNER_ID cannot be 0. Set it to your own Discord user ID.")
