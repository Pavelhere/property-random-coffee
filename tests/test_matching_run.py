# -*- coding: utf-8 -*-
"""Weekly match run: cron auth + atomic once-per-week guard."""

import uuid

from models.user import User


def _signup(app_main, name, email, meet_group="coffee"):
    user = User(
        id=str(uuid.uuid4()), username=name, full_name=name, email=email,
        loc="community", meet_group=meet_group, pause_in_weeks="0",
        bio=f"{name} bio", extra_info="", gender_pref="any",
    )
    app_main.user_repo.add(user)
    return user


def _run(client, admin_token, qs=""):
    return client.post(
        f"/admin/matches{qs}",
        headers={"Authorization": f"Bearer {admin_token}"},
    )


def test_cron_requires_auth(client):
    assert client.post("/admin/matches").status_code == 401
    res = client.post("/admin/matches", headers={"Authorization": "Bearer wrong"})
    assert res.status_code == 401


def test_run_pairs_and_emails(client, app_main, sent_emails, admin_token):
    u1 = _signup(app_main, "Jane", "jane@example.com")
    u2 = _signup(app_main, "Sam", "sam@example.com")

    res = _run(client, admin_token)
    assert res.status_code == 200
    data = res.get_json()
    assert data["status"] == "ok"
    assert data["proposals_sent"] == 1  # one meet, both sides emailed

    proposals = [m for m in sent_emails if "match this week" in m["subject"]]
    assert {m["to"] for m in proposals} == {"jane@example.com", "sam@example.com"}

    meets = app_main.meet_repo.list()
    assert len(meets) == 1
    assert {meets[0].uid1, meets[0].uid2} == {u1.id, u2.id}
    assert meets[0].proposal_sent is True


def test_second_run_same_week_skipped(client, app_main, sent_emails, admin_token):
    _signup(app_main, "Jane", "jane@example.com")
    _signup(app_main, "Sam", "sam@example.com")

    assert _run(client, admin_token).get_json()["status"] == "ok"
    emails_after_first = len(sent_emails)

    # cron retries / double-fire
    for _ in range(3):
        assert _run(client, admin_token).get_json()["status"] == "skipped"

    assert len(sent_emails) == emails_after_first
    assert len(app_main.meet_repo.list()) == 1


def test_force_reruns_but_never_duplicates_emails(client, app_main, sent_emails, admin_token):
    _signup(app_main, "Jane", "jane@example.com")
    _signup(app_main, "Sam", "sam@example.com")

    _run(client, admin_token)
    emails_after_first = len(sent_emails)

    res = _run(client, admin_token, "?force=1")
    assert res.get_json()["status"] == "ok"
    # both users already matched this season → no new meet, no new emails
    assert len(app_main.meet_repo.list()) == 1
    assert len(sent_emails) == emails_after_first


def test_paused_users_excluded(client, app_main, sent_emails, admin_token):
    from datetime import date, timedelta
    _signup(app_main, "Jane", "jane@example.com")
    paused = _signup(app_main, "Sam", "sam@example.com")
    paused.paused_until = date.today() + timedelta(weeks=2)
    app_main.user_repo.update(paused)

    res = _run(client, admin_token)
    assert res.status_code == 200
    # only one active user in the group → nobody to pair, no proposals
    assert res.get_json()["proposals_sent"] == 0
    assert all("match this week" not in m["subject"] for m in sent_emails)


def test_claim_is_atomic(app_main):
    svc = app_main.matching_service
    assert svc._claim_run("999901") is True
    assert svc._claim_run("999901") is False  # unique index rejects second claim
    assert svc._claim_run("999902") is True   # different week claims fine
