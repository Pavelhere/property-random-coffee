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

## Current state (2026-06-01)

MVP is built and runs locally. Single-page signup → confirmation email → weekly match
email. Admin panel lists participants, triggers matching, exports CSV, and sends a
sample test email.

**Pending to launch:**
1. Add Resend DNS records to stratora.one, then set SMTP creds in `resources/config.yml`
   and flip `notifications.dryRun: false` (see DECISIONS.md 2026-06-01).
2. Deploy (Dockerfile exists; Railway / Render / Fly.io are options).
3. Wire the property id from the signup link param into `loc` (still defaults to "community").

## Run locally

```bash
# MySQL (port 3308, matches config.yml)
docker start rcb-mysql-dev   # or: docker run -d --name rcb-mysql-dev \
  #   -e MYSQL_ROOT_PASSWORD=root -e MYSQL_DATABASE=coffee -p 3308:3306 mysql:8.0

# deps live in a uv venv (.venv); mysqlclient needs mysql-client + pkg-config + zstd via brew
DATABASE_PASSWORD=root PYTHONPATH=src FLASK_APP=src/main.py .venv/bin/flask run --port 5000
```

App: http://127.0.0.1:5000 — admin: http://127.0.0.1:5000/admin?token=change-this-secret
(Use `127.0.0.1`, not `localhost`.)

Schema note: SQLAlchemy `create_all()` does NOT alter existing tables. When adding a
column to `src/models/user.py`, also `ALTER TABLE user ADD COLUMN ...` on the live DB.

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
