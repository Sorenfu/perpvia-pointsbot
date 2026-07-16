import os
from dotenv import load_dotenv

load_dotenv()

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN", "").strip()
DATABASE_URL = os.getenv("DATABASE_URL", "").strip()
OWNER_ID = int(os.getenv("OWNER_ID", "0") or "0")
ADMIN_ROLE_ID = int(os.getenv("ADMIN_ROLE_ID", "0") or "0")
ENVIRONMENT = os.getenv("ENVIRONMENT", "production")
ERROR_WEBHOOK_URL = os.getenv("ERROR_WEBHOOK_URL", "").strip()

# NFT holder verification (optional). Leave empty to keep the feature disabled/hidden.
NFT_CONTRACT_ADDRESS = os.getenv("NFT_CONTRACT_ADDRESS", "").strip()
NFT_RPC_URL = os.getenv("NFT_RPC_URL", "").strip()
NFT_HOLDER_ROLE_ID = int(os.getenv("NFT_HOLDER_ROLE_ID", "0") or "0")

# Advanced task review queue (optional). Leave empty to keep /submit_task hidden/disabled.
TASK_REVIEW_CHANNEL_ID = int(os.getenv("TASK_REVIEW_CHANNEL_ID", "0") or "0")

if not DISCORD_TOKEN:
    raise RuntimeError("Missing DISCORD_TOKEN environment variable")

if not DATABASE_URL:
    raise RuntimeError("Missing DATABASE_URL environment variable")

if OWNER_ID == 0:
    raise RuntimeError("Missing OWNER_ID environment variable")
