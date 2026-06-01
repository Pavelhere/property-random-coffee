# Decision Log

Append-only record of the meaningful decisions on this project — context, what we
chose, why, and how it turned out. Newest entries at the bottom. Read this to
understand *why* the code looks the way it does before changing it.

Entry format:

```
## YYYY-MM-DD — <short title>
**Context:** what prompted this
**Decision:** what we chose
**Why:** reasoning, alternatives, trade-offs
**Result:** what happened / current status
```

---

## 2026-04-29 — Rebuild as a Flask tenant-matching app

**Context:** The repo started life as `random_coffee_slack`, a Slack bot that paired
community members for weekly coffee. The product direction moved to apartment
communities (residents, not Slack workspaces), sold B2B to property managers.
**Decision:** Rebuild around a Flask web app + email-first notifications. Tenants
join via `/join`, admins trigger weekly matches and export CSV from the admin area,
proposal responses handled via signed `/respond` links. Legacy Slack code preserved
in `src/legacy_slack_main.py`.
**Why:** Residents won't be in a shared Slack. Email is the universal channel and
needs no app install. Keeping the legacy file avoids losing working logic.
**Result:** Shipped as the single commit "Rebuild as Flask-based tenant matching app
for apartment communities." Foundation for everything since.

## 2026-05-20 — One-page signup, no email verification (MVP)

**Context:** Original plan (Ultraplan) was a two-stage flow: enter email → receive
OTP code → verify → fill profile. Goal shifted to "launch today to test."
**Decision:** Collapse to a single page. Resident fills everything at once (name,
email, preferences, bio), submits, gets a confirmation email, and receives a match
the next Monday. No OTP / email verification.
**Why:** Verification adds friction and build time for near-zero MVP value at one
property with a known resident list. Can add later before public/multi-property.
**Result:** Single `/join` form live. Verification explicitly deferred.

## 2026-05-20 — Property is an internal field, not shown to residents

**Context:** Needed to support multiple properties eventually (Preston Ridge first),
but residents shouldn't pick or see their property.
**Decision:** Store property as the internal `loc` field on the user, intended to be
set from the QR-code / signup link param. Not surfaced in the form.
**Why:** Residents scan a property-specific QR/link; the property is implied. Keeps
the form clean and prevents cross-property mismatches.
**Result:** `loc` repurposed for property id. Matching groups within a property.
(Note: link-param wiring still to come; currently defaults to "community".)

## 2026-05-20 — Repurpose `meet_group` from building → activity type

**Context:** `meet_group` originally grouped people by building (Skyline Tower,
Riverside Lofts). New model groups by preferred activity.
**Decision:** `meet_group` values are now `coffee` / `walking` / `playdate`. The
matching service already groups by `meet_group`, so people are paired within the
same activity with no matching-logic changes.
**Why:** Pairing people who want the same kind of meetup is the actual product value.
Reusing the existing column avoids schema churn and keeps matching intact.
**Result:** Config (`resources/config.yml`) groups replaced with the three activities.

## 2026-05-20 — Single-select activity (radio), not multi-select

**Context:** The landing-page design (`community_coffee_landing_page_preview.jsx`)
showed activity as multiple checkboxes.
**Decision:** Keep activity as a single choice (radio buttons), not multi-select.
**Why:** The matching engine groups by one `meet_group` value per user. Multi-select
would break that model and require a rework. Single-select ships now; revisit if
demand shows people want several activity types.
**Result:** Form uses radio buttons. Logged as a known divergence from the design.

## 2026-05-20 — Richer profile: gender_pref, bio, life-context

**Context:** Pitch deck and design called for a bio, "comfortable meeting" preference,
and life-context tags. Backend lacked these.
**Decision:** Add `gender_pref` (any / women / men), `bio` (max 250 chars, enforced
front + back), and reuse `extra_info` for comma-joined life-context checkboxes
(New here / Works from home / Has kids / Pet owner). Consent checkbox required.
**Why:** These drive better, safer matches and match the deck's promise. 250-char bio
per Pavel's call. Comma-joined tags render as pills in the match email.
**Result:** Columns added to `user` table (live MySQL ALTERed too). Form + admin panel
updated. Verified end-to-end with a test signup (Jane Kim).

## 2026-05-20 — Confirmation email + admin "send test email"

**Context:** Pavel wanted to see exactly what residents receive and to verify email
plumbing before launch.
**Decision:** Send a confirmation email immediately on signup. Add an admin "Send
test match email" button that fires a sample match email using Marcus Lee fake data
from the deck.
**Why:** De-risks the email path and lets Pavel preview the invitation without running
a real matching cycle.
**Result:** Both working in dry-run mode (emails logged, not sent). Match email
template now includes bio, activity, and life-context pills.

## 2026-06-01 — Resend over stratora.one for email delivery

**Context:** Needed real SMTP to actually send mail. Pavel has a stratora.one business
address.
**Decision:** Use Resend (free tier: 3k/mo, 100/day) with `stratora.one` as the
sending domain, via Resend's SMTP bridge. No code change — just fill
`resources/config.yml` and set `notifications.dryRun: false`.
**Why:** Fastest path (~5 min DNS), generous free tier far exceeds MVP volume, and
the SMTP bridge means zero code changes. One-property scale carries no reputation risk.
**Result:** PENDING — waiting on Pavel to add Resend's DNS records to stratora.one,
then wire config and run a live test.

## 2026-06-01 — Adopt a git-committed decision log + project CLAUDE.md

**Context:** Many Claude Code sessions, often launched from the home directory, so
they scattered into one bucket with ~20 unrelated sessions. Hard to find the right
session or recover the reasoning behind past choices.
**Decision:** Keep this `docs/DECISIONS.md` as the durable source of truth, plus a
slim root `CLAUDE.md` (current state + run commands + pointer here), and adopt the
habit of launching Claude from the project folder. Manual maintenance — append + commit
when a real decision is made. No hooks yet.
**Why:** A version-controlled markdown log is searchable, durable, travels with the
repo, and is independent of Claude's session storage. Beats mining `.jsonl`
transcripts or third-party tools.
**Result:** This file created and seeded. CLAUDE.md added. Workflow in effect.
