CREATE TABLE IF NOT EXISTS users (
    discord_id BIGINT PRIMARY KEY,
    username TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);

ALTER TABLE users ADD COLUMN IF NOT EXISTS username TEXT;
ALTER TABLE users ADD COLUMN IF NOT EXISTS created_at TIMESTAMP DEFAULT NOW();

CREATE TABLE IF NOT EXISTS points (
    id SERIAL PRIMARY KEY,
    discord_id BIGINT NOT NULL,
    amount INTEGER NOT NULL,
    type TEXT NOT NULL,
    reason TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_points_discord_id ON points(discord_id);

CREATE TABLE IF NOT EXISTS tasks (
    id SERIAL PRIMARY KEY,
    name TEXT NOT NULL,
    description TEXT,
    reward INTEGER NOT NULL DEFAULT 0,
    status TEXT DEFAULT 'ACTIVE',
    category TEXT NOT NULL DEFAULT 'BASIC',
    starts_at TIMESTAMP,
    ends_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT NOW()
);

ALTER TABLE tasks ADD COLUMN IF NOT EXISTS category TEXT NOT NULL DEFAULT 'BASIC';
ALTER TABLE tasks ADD COLUMN IF NOT EXISTS starts_at TIMESTAMP;
ALTER TABLE tasks ADD COLUMN IF NOT EXISTS ends_at TIMESTAMP;

CREATE TABLE IF NOT EXISTS user_tasks (
    id SERIAL PRIMARY KEY,
    discord_id BIGINT NOT NULL,
    task_id INTEGER NOT NULL,
    granted_by BIGINT,
    note TEXT,
    awarded_points INTEGER,
    completed_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(discord_id, task_id)
);

ALTER TABLE user_tasks ADD COLUMN IF NOT EXISTS granted_by BIGINT;
ALTER TABLE user_tasks ADD COLUMN IF NOT EXISTS note TEXT;
ALTER TABLE user_tasks ADD COLUMN IF NOT EXISTS awarded_points INTEGER;

CREATE TABLE IF NOT EXISTS checkins (
    id SERIAL PRIMARY KEY,
    discord_id BIGINT NOT NULL,
    checkin_date DATE NOT NULL,
    created_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(discord_id, checkin_date)
);

CREATE TABLE IF NOT EXISTS products (
    id SERIAL PRIMARY KEY,
    name TEXT NOT NULL,
    description TEXT,
    price INTEGER NOT NULL,
    role_id BIGINT,
    stock INTEGER,
    status TEXT DEFAULT 'ACTIVE',
    created_at TIMESTAMP DEFAULT NOW()
);

ALTER TABLE products ADD COLUMN IF NOT EXISTS stock INTEGER;

CREATE TABLE IF NOT EXISTS orders (
    id SERIAL PRIMARY KEY,
    discord_id BIGINT NOT NULL,
    product_id INTEGER NOT NULL,
    price INTEGER NOT NULL,
    status TEXT DEFAULT 'SUCCESS',
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_orders_discord_id ON orders(discord_id);

CREATE TABLE IF NOT EXISTS invite_codes (
    code TEXT PRIMARY KEY,
    inviter_discord_id BIGINT NOT NULL,
    uses INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS referrals (
    id SERIAL PRIMARY KEY,
    inviter_discord_id BIGINT NOT NULL,
    invitee_discord_id BIGINT UNIQUE NOT NULL,
    invite_code TEXT,
    verified BOOLEAN DEFAULT FALSE,
    rewarded BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT NOW(),
    rewarded_at TIMESTAMP
);

CREATE TABLE IF NOT EXISTS message_activity (
    discord_id BIGINT NOT NULL,
    activity_date DATE NOT NULL,
    points_earned INTEGER NOT NULL DEFAULT 0,
    last_rewarded_at TIMESTAMP,
    PRIMARY KEY (discord_id, activity_date)
);

CREATE TABLE IF NOT EXISTS admin_logs (
    id SERIAL PRIMARY KEY,
    admin_discord_id BIGINT NOT NULL,
    action TEXT NOT NULL,
    detail TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS task_submissions (
    id SERIAL PRIMARY KEY,
    discord_id BIGINT NOT NULL,
    task_id INTEGER NOT NULL,
    proof TEXT,
    status TEXT NOT NULL DEFAULT 'PENDING',
    reviewed_by BIGINT,
    review_note TEXT,
    message_id BIGINT,
    awarded_points INTEGER,
    created_at TIMESTAMP DEFAULT NOW(),
    reviewed_at TIMESTAMP
);

ALTER TABLE task_submissions ADD COLUMN IF NOT EXISTS awarded_points INTEGER;

CREATE INDEX IF NOT EXISTS idx_task_submissions_discord_id ON task_submissions(discord_id);
CREATE UNIQUE INDEX IF NOT EXISTS idx_task_submissions_pending ON task_submissions(discord_id, task_id) WHERE status='PENDING';

CREATE TABLE IF NOT EXISTS wallet_bindings (
    discord_id BIGINT PRIMARY KEY,
    wallet_address TEXT NOT NULL,
    verified_at TIMESTAMP DEFAULT NOW()
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_wallet_bindings_address ON wallet_bindings(wallet_address);

CREATE TABLE IF NOT EXISTS wallet_nonces (
    discord_id BIGINT PRIMARY KEY,
    wallet_address TEXT NOT NULL,
    nonce TEXT NOT NULL,
    expires_at TIMESTAMP NOT NULL,
    created_at TIMESTAMP DEFAULT NOW()
);
