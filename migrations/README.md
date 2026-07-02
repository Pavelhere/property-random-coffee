# Migrations

SQLAlchemy `create_all()` creates missing **tables** but never alters existing ones.
Every schema change to an existing table ships as a numbered `.sql` file here and is
applied manually (or via deploy step) to the live database, in order:

```bash
mysql -h 127.0.0.1 -P 3308 -u root -proot coffee < migrations/00X_name.sql
```

Rules:

- One file per change, numbered, never edited after it has been applied anywhere.
- Idempotent where MySQL allows (use `IF NOT EXISTS` for indexes/tables; for
  `ADD COLUMN` on MySQL 8 use `IF NOT EXISTS` too).
- The model change in `src/models/` and its migration file land in the same commit.

`000_baseline.sql` documents the schema as of 2026-07-02 (pre-launch-readiness pass)
for reference; it is NOT meant to be applied.
