-- 002: user.gender — required to enforce the "women only / men only"
-- matching preference (previously collected but unenforceable).
-- Existing residents default to 'unspecified' (matches only "no preference").

ALTER TABLE user ADD COLUMN gender VARCHAR(12) NULL DEFAULT 'unspecified';
