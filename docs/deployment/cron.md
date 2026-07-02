# Weekly matching cron

There is **no in-process scheduler**. Matching runs when something POSTs the
admin endpoint. That something is a platform cron.

## The call

```bash
curl -X POST -H "Authorization: Bearer $ADMIN_TOKEN" \
  https://<app-host>/admin/matches
```

- Safe to re-fire: the run claims a unique `MATCH_RUN_{season}` row in `meta`
  atomically; a second call the same ISO week returns `{"status":"skipped"}`.
- `?force=1` overrides the guard (re-pairing is still bounded: users already
  matched this season are skipped, and `proposal_sent` prevents duplicate
  emails).
- Dry-run preview (no sends, no writes): `POST /admin/matches?dry_run=1`
  or the "Preview pairs" button in the admin panel.

## Schedule

Mondays **09:00 in the property's timezone** (`community.timezone` in
config, default America/Chicago). Cron services usually take UTC — convert
(09:00 America/Chicago = 14:00 UTC in summer, 15:00 UTC in winter; or just
schedule 15:00 UTC year-round and accept 9/10am drift).

- **Railway:** cron jobs in the service settings, schedule `0 15 * * 1`,
  command `curl -X POST -H "Authorization: Bearer $ADMIN_TOKEN" https://<app>/admin/matches`
- **Render:** Cron Job service type, same command.
- **cron-job.org** (works with any host): POST job with the Authorization
  header, Mondays 09:00 America/Chicago (it supports timezones natively).

## Failure visibility

The response JSON reports `proposals_sent`. The admin panel shows run history
(match runs + skipped users). If Monday passes and the run row for the week
is missing, the cron did not fire — check the cron service first, app second.
