# Property Random Coffee

A weekly neighbor-matching program for apartment communities, sold B2B to property
managers. Residents sign up once via a QR code / link; every Monday each resident gets
a personal email introduction to one neighbor (their name, bio, and a suggested way to
meet — coffee, a walk, or a playdate) and accepts or declines in one tap. No app, no
public directory. First property: Preston Ridge.

## Decision history — READ THIS FIRST

The *why* behind every choice lives in **`docs/DECISIONS.md`** (append-only log).
Before changing how something works, read the relevant entry. When we make a real
decision, append a new entry and commit it (`docs: log decision — <title>`).

## Current state (2026-07-02)

Launch-readiness pass complete (see DECISIONS.md 2026-07-02): signup → confirmation
email → weekly match email → scanner-safe accept/decline confirm page → connection
email. Gender preferences enforced in pairing; signed pause/unsubscribe and
profile-edit links; per-complex scoping via `/?p=<complex>`; match-run audit trail +
admin dry-run preview. 72 SQLite tests + 3 MySQL integration tests (`pytest`,
`pytest -m mysql`).

Matching is triggered by a platform cron POSTing `/admin/matches` (Bearer
ADMIN_TOKEN) — there is NO in-process scheduler. See `docs/deployment/cron.md`.

**Pending to launch:**
1. Add Resend DNS records to stratora.one, set `RESEND_API_KEY`, and set
   `NOTIFICATIONS_DRY_RUN=false` in the deployed env (see DECISIONS.md 2026-06-01).
2. Deploy (Dockerfile exists; Railway / Render / Fly.io are options) + configure the
   Monday cron per `docs/deployment/cron.md`.
3. Before the first real Monday: use the admin "Preview pairs (dry run)" button to
   inspect pairs, then run for real.

## Run locally

```bash
# MySQL (port 3308, matches config.yml)
docker start rcb-mysql-dev   # or: docker run -d --name rcb-mysql-dev \
  #   -e MYSQL_ROOT_PASSWORD=root -e MYSQL_DATABASE=coffee -p 3308:3306 mysql:8.0

# deps live in a uv venv (.venv); mysqlclient needs mysql-client + pkg-config + zstd via brew
# Secrets come from env, never from config.yml:
DATABASE_PASSWORD=root ADMIN_TOKEN=dev-admin RESPONSE_SECRET=dev-secret \
  PYTHONPATH=src FLASK_APP=src/main.py .venv/bin/flask run --port 5000
```

App: http://127.0.0.1:5000 — admin: http://127.0.0.1:5000/admin?token=dev-admin
(Use `127.0.0.1`, not `localhost`.)

Email is dry-run by default (`notifications.dryRun: true` — emails are logged, not
sent). Real sending only in the deployed env via `NOTIFICATIONS_DRY_RUN=false` +
`RESEND_API_KEY`.

Schema note: SQLAlchemy `create_all()` does NOT alter existing tables. Every change
to an existing table ships as a numbered file in `migrations/` (see its README) and
is applied manually to the live DB.

## Sessions

Launch `claude` from **this folder** (not the home directory) so `/resume` shows only
this project's sessions.

More local SQL/snippets in `docs/details.md`.

## Skill routing

When the user's request matches an available skill, ALWAYS invoke it using the Skill
tool as your FIRST action. Do NOT answer directly, do NOT use other tools first.
The skill has specialized workflows that produce better results than ad-hoc answers.

Key routing rules:
- Product ideas, "is this worth building", brainstorming → invoke office-hours
- Bugs, errors, "why is this broken", 500 errors → invoke investigate
- Ship, deploy, push, create PR → invoke ship
- QA, test the site, find bugs → invoke qa
- Code review, check my diff → invoke review
- Update docs after shipping → invoke document-release
- Weekly retro → invoke retro
- Design system, brand → invoke design-consultation
- Visual audit, design polish → invoke design-review
- Architecture review → invoke plan-eng-review
- Save progress, checkpoint, resume → invoke context-save / context-restore
- Code quality, health check → invoke health
