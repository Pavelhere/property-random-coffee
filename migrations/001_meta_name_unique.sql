-- 001: unique index on meta.name
-- The weekly match run claims a unique MATCH_RUN_{season} row as an atomic
-- lock (insert-or-fail). Requires name to be unique.
-- Dedupe first (keep the oldest row per name), then add the index.

DELETE m1 FROM meta m1
INNER JOIN meta m2 ON m1.name = m2.name AND m1.id > m2.id;

ALTER TABLE meta ADD UNIQUE INDEX uq_meta_name (name);
