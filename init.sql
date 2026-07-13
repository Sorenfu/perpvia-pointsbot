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
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS user_tasks (
    id SERIAL PRIMARY KEY,
    discord_id BIGINT NOT NULL,
    task_id INTEGER NOT NULL,
    completed_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(discord_id, task_id)
);

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
    status TEXT DEFAULT 'ACTIVE',
    created_at TIMESTAMP DEFAULT NOW()
);

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

CREATE TABLE IF NOT EXISTS admin_logs (
    id SERIAL PRIMARY KEY,
    admin_discord_id BIGINT NOT NULL,
    action TEXT NOT NULL,
    detail TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);
