# -*- coding: utf-8 -*-
"""Dry-run preview + match-run audit trail.

The founder must be able to see Monday's pairs BEFORE any email exists,
and answer 'did Monday actually happen?' from the admin panel.
"""

import uuid

from models.user import User


def _user(app_main, name, email):
    user = User(
        id=str(uuid.uuid4()), username=name, full_name=name, email=email,
        loc="community", meet_group="coffee", pause_in_weeks="0",
        bio="b", extra_info="", gender="woman", gender_pref="any",
    )
    app_main.user_repo.add(user)
    return user


def _post(client, admin_token, qs=""):
    return client.post(f"/admin/matches{qs}",
                       headers={"Authorization": f"Bearer {admin_token}"})


def test_dry_run_has_zero_side_effects(client, app_main, sent_emails, admin_token):
    _user(app_main, "Jane", "jane@example.com")
    _user(app_main, "Ann", "ann@example.com")

    res = _post(client, admin_token, "?dry_run=1")
    data = res.get_json()
    assert data["status"] == "dry_run"
    assert len(data["pairs"]) == 1
    emails_in_pair = {data["pairs"][0]["a"]["email"], data["pairs"][0]["b"]["email"]}
    assert emails_in_pair == {"jane@example.com", "ann@example.com"}

    # nothing persisted, nothing sent, week not claimed
    assert app_main.meet_repo.list() == []
    assert sent_emails == []

    # the real run afterwards works and is NOT 'skipped'
    real = _post(client, admin_token).get_json()
    assert real["status"] == "ok"
    assert real["proposals_sent"] == 1


def test_dry_run_repeatable(client, app_main, admin_token):
    _user(app_main, "Jane", "jane@example.com")
    _user(app_main, "Ann", "ann@example.com")
    for _ in range(3):
        assert _post(client, admin_token, "?dry_run=1").get_json()["status"] == "dry_run"
    assert app_main.meet_repo.list() == []


def test_runs_are_recorded(client, app_main, admin_token):
    _user(app_main, "Jane", "jane@example.com")
    _user(app_main, "Ann", "ann@example.com")

    _post(client, admin_token, "?dry_run=1")
    _post(client, admin_token)

    runs = app_main.match_run_repo.list()
    assert len(runs) == 2
    real = [r for r in runs if not r.dry_run][0]
    dry = [r for r in runs if r.dry_run][0]
    assert real.pairs_created == 1 and real.proposals_sent == 1
    assert dry.pairs_created == 1 and dry.proposals_sent == 0


def test_unmatched_visible_in_run_record(client, app_main, admin_token):
    _user(app_main, "Solo", "solo@example.com")  # odd one out, nobody to pair
    _post(client, admin_token)
    runs = app_main.match_run_repo.list()
    assert runs and "solo@example.com" in (runs[0].unmatched or "")


def test_admin_panel_shows_run_history(client, app_main, admin_token):
    _user(app_main, "Jane", "jane@example.com")
    _user(app_main, "Ann", "ann@example.com")
    _post(client, admin_token)

    res = client.get(f"/admin?token={admin_token}")
    assert res.status_code == 200
    assert b"Match runs" in res.data
    assert b"Preview pairs" in res.data
