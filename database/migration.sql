-- Recommended production timestamp type
ALTER TABLE daily_checkins
ALTER COLUMN created_at
TYPE TIMESTAMPTZ
USING created_at AT TIME ZONE 'UTC';
