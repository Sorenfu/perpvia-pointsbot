CREATE TABLE IF NOT EXISTS users (
    discord_id BIGINT PRIMARY KEY,
    points BIGINT NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS point_transactions (
    id BIGSERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL,
    amount BIGINT NOT NULL,
    source TEXT NOT NULL,
    reason TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS daily_checkins (
    id BIGSERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL,
    reward BIGINT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS message_rewards (
    id BIGSERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL,
    amount BIGINT NOT NULL,
    reward_date DATE NOT NULL DEFAULT CURRENT_DATE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS invites (
    id BIGSERIAL PRIMARY KEY,
    inviter_id BIGINT NOT NULL,
    invitee_id BIGINT NOT NULL UNIQUE,
    invite_code TEXT,
    status TEXT NOT NULL DEFAULT 'pending',
    reward_claimed BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    verified_at TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS role_reward_history (
    id BIGSERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL,
    role_id BIGINT NOT NULL,
    role_name TEXT,
    reward BIGINT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(user_id, role_id)
);

CREATE TABLE IF NOT EXISTS products (
    id BIGSERIAL PRIMARY KEY,
    name TEXT NOT NULL,
    description TEXT DEFAULT '',
    price BIGINT NOT NULL,
    product_type TEXT NOT NULL DEFAULT 'ITEM',
    role_id BIGINT,
    stock INT NOT NULL DEFAULT -1,
    status TEXT NOT NULL DEFAULT 'active',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS orders (
    id BIGSERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL,
    product_id BIGINT NOT NULL,
    cost BIGINT NOT NULL,
    status TEXT NOT NULL DEFAULT 'created',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS audit_logs (
    id BIGSERIAL PRIMARY KEY,
    operator_id BIGINT,
    action TEXT NOT NULL,
    target_id BIGINT,
    payload TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
