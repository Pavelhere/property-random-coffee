# TODOS

Deferred work with full context. Format: What / Why / Pros / Cons / Context / Depends on.

---

## Multi-tenant complexes: per-property admin + master admin

**What:** Turn the app into a proper multi-tenant system at the *complex* level (not
building): each residential complex (Preston Ridge, Cary Greens, …) is an isolated
tenant with its own admin access and dashboard; Pavel is master admin across all.

**Why:** Different complexes belong to different management groups. Their residents,
matches, metrics, and CSV exports must never mix. A property manager should manage
only their own complex; Pavel needs the cross-tenant view.

**Pros:** Unlocks selling complex #2 without a scramble; is the natural data model for
the manager dashboard (design doc Approach B, phase 2); per-tenant metrics become the
"fast proof number" per buyer.

**Cons:** Real auth/role work (per-tenant tokens or logins, scoped queries everywhere,
master role). Speculative until a second complex actually commits — building it now
violates the design doc's "validate demand first" rule.

**Context (2026-07-01):** Groundwork ships in the current launch-readiness pass: the
signup link carries the complex id (`?p=<complex>`), stored in the existing `loc`
column; matching, the admin participant table, and CSV export filter by `loc`. So all
data is tenant-tagged from the first signup and this TODO is purely the access/roles
layer on top. Also bundle here: push repo filtering down into SQL (meet/user repos
currently load-all-then-filter-in-Python; fine at n=40, not at 10 complexes) and fix
the `_serialize_match` N+1 in the admin matches view.

**Depends on / blocked by:** A second complex signing (paid pilot or LOI). Do not
build before that — see docs DECISIONS.md and the 2026-06-17 design doc's failure
path.
