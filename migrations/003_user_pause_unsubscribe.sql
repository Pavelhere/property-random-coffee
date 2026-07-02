-- 003: real pause + unsubscribe state.
-- paused_until: date-based pause (self-healing — no decrement job needed;
-- matching simply skips users whose date is in the future).
-- unsubscribed: suppresses ALL email types and matching, permanently,
-- until the resident explicitly re-joins.
-- pause_in_weeks is retired (column kept for now, no longer read).

ALTER TABLE user ADD COLUMN paused_until DATE NULL;
ALTER TABLE user ADD COLUMN unsubscribed BOOLEAN NOT NULL DEFAULT FALSE;
