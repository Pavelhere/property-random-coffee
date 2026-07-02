# -*- coding: utf-8 -*-
# Regression: ISSUE-003 — the admin "Preview pairs (dry run)" button dumped
# raw JSON in the browser with no way back to the admin panel. The preview is
# the founder's pre-Monday safety check; it must be readable.
# Found by /qa on 2026-07-02
# Report: .gstack/qa-reports/qa-report-127-0-0-1-2026-07-02.md

import uuid

from models.user import User


def _user(app_main, name, email):
    user = User(
        id=str(uuid.uuid4()), username=name, full_name=name, email=email,
        loc="preston-ridge", meet_group="coffee", pause_in_weeks="0",
        bio="b", extra_info="", gender="woman", gender_pref="any",
    )
    app_main.user_repo.add(user)
    return user


def test_browser_dry_run_gets_readable_preview(client, app_main, admin_token):
    _user(app_main, "Jane Kim", "jane@example.com")
    _user(app_main, "Ann Lee", "ann@example.com")

    res = client.post(
        f"/admin/matches?token={admin_token}&dry_run=1",
        headers={"Accept": "text/html"},  # what a browser form post sends
    )
    assert res.status_code == 200
    assert res.mimetype == "text/html"
    assert b"Pair preview" in res.data
    assert b"Jane Kim" in res.data and b"Ann Lee" in res.data
    assert b"Back to admin" in res.data
    # still a dry run: nothing persisted
    assert app_main.meet_repo.list() == []


def test_cron_and_json_clients_still_get_json(client, app_main, admin_token):
    _user(app_main, "Jane Kim", "jane@example.com")
    _user(app_main, "Ann Lee", "ann@example.com")

    # curl-style (Accept: */*) → JSON
    res = client.post("/admin/matches?dry_run=1",
                      headers={"Authorization": f"Bearer {admin_token}"})
    assert res.mimetype == "application/json"
    assert res.get_json()["status"] == "dry_run"

    # real (non-dry) browser run also stays JSON — only the preview is a page
    res = client.post(f"/admin/matches?token={admin_token}",
                      headers={"Accept": "text/html"})
    assert res.mimetype == "application/json"
    assert res.get_json()["status"] == "ok"
