# -*- coding: utf-8 -*-
"""/preferences: signed pause + unsubscribe self-service.

Properties:
- links are signed and expiring; tampered/expired tokens do nothing
- GET is read-only (scanner-safe); POST changes state
- pause is a date — self-healing, no decrement job (a missed cron week
  cannot extend anyone's pause)
- unsubscribe suppresses matching AND every email type
"""

import time
import uuid
from datetime import date, timedelta
from urllib.parse import urlparse, parse_qs

from models.user import User
from models.meet import Meet
from utils import links


def _user(app_main, name, email):
    user = User(
        id=str(uuid.uuid4()), username=name, full_name=name, email=email,
        loc="community", meet_group="coffee", pause_in_weeks="0",
        bio=f"{name} bio", extra_info="", gender="woman", gender_pref="any",
    )
    app_main.user_repo.add(user)
    return user


def _prefs_qs(app_main, uid):
    url = links.preferences_url("http://testserver", "test-response-secret", uid)
    q = parse_qs(urlparse(url).query)
    return {k: v[0] for k, v in q.items()}


def _post_prefs(client, app_main, uid, action):
    data = _prefs_qs(app_main, uid)
    data["action"] = action
    return client.post("/preferences", data=data)


# --- token safety -----------------------------------------------------------

def test_tampered_or_expired_link_rejected(client, app_main):
    u = _user(app_main, "Jane", "jane@example.com")
    params = _prefs_qs(app_main, u.id)

    bad = dict(params, signature="forged")
    assert client.get("/preferences", query_string=bad).status_code == 400

    expired_sig = links._sig("test-response-secret", "prefs", u.id, int(time.time()) - 10)
    expired = dict(uid=u.id, exp=str(int(time.time()) - 10), signature=expired_sig)
    assert client.get("/preferences", query_string=expired).status_code == 400

    # respond-token can't be replayed against /preferences (purpose namespace)
    respond_sig = app_main.response_service.sign("1", u.id, "accept")
    cross = dict(uid=u.id, exp=params["exp"], signature=respond_sig)
    assert client.get("/preferences", query_string=cross).status_code == 400


def test_get_is_read_only(client, app_main):
    u = _user(app_main, "Jane", "jane@example.com")
    res = client.get("/preferences", query_string=_prefs_qs(app_main, u.id))
    assert res.status_code == 200
    fresh = app_main.user_repo.get_by_id(u.id)
    assert fresh.paused_until is None and fresh.unsubscribed is False


# --- pause lifecycle ---------------------------------------------------------

def test_pause_sets_date_and_excludes_from_matching(client, app_main, admin_token):
    u1 = _user(app_main, "Jane", "jane@example.com")
    _user(app_main, "Ann", "ann@example.com")

    res = _post_prefs(client, app_main, u1.id, "pause_2")
    assert res.status_code == 200
    fresh = app_main.user_repo.get_by_id(u1.id)
    assert fresh.paused_until == date.today() + timedelta(weeks=2)

    run = client.post("/admin/matches",
                      headers={"Authorization": f"Bearer {admin_token}"}).get_json()
    assert run["proposals_sent"] == 0  # only Ann left in the pool


def test_pause_self_heals_without_cron(client, app_main, admin_token):
    u1 = _user(app_main, "Jane", "jane@example.com")
    _user(app_main, "Ann", "ann@example.com")

    # paused in the past — as if two weeks elapsed with NO cron runs at all
    u1.paused_until = date.today() - timedelta(days=1)
    app_main.user_repo.update(u1)

    run = client.post("/admin/matches",
                      headers={"Authorization": f"Bearer {admin_token}"}).get_json()
    assert run["proposals_sent"] == 1  # back in automatically


def test_resume_clears_pause(client, app_main):
    u = _user(app_main, "Jane", "jane@example.com")
    _post_prefs(client, app_main, u.id, "pause_4")
    _post_prefs(client, app_main, u.id, "resume")
    fresh = app_main.user_repo.get_by_id(u.id)
    assert fresh.paused_until is None and fresh.unsubscribed is False


# --- unsubscribe -------------------------------------------------------------

def test_unsubscribe_blocks_matching_and_all_emails(client, app_main, sent_emails, admin_token):
    u1 = _user(app_main, "Jane", "jane@example.com")
    _user(app_main, "Ann", "ann@example.com")

    _post_prefs(client, app_main, u1.id, "unsubscribe")
    assert app_main.user_repo.get_by_id(u1.id).unsubscribed is True

    run = client.post("/admin/matches",
                      headers={"Authorization": f"Bearer {admin_token}"}).get_json()
    assert run["proposals_sent"] == 0
    assert all(m["to"] != "jane@example.com" for m in sent_emails)


def test_unsubscribe_suppresses_connection_email_mid_flow(client, app_main, sent_emails):
    u1 = _user(app_main, "Jane", "jane@example.com")
    u2 = _user(app_main, "Ann", "ann@example.com")
    meet = app_main.meet_repo.add(Meet(season="202627", uid1=u1.id, uid2=u2.id))

    sig1 = app_main.response_service.sign(str(meet.id), u1.id, "accept")
    client.post("/respond", data={"meet_id": str(meet.id), "uid": u1.id,
                                  "action": "accept", "signature": sig1})

    # u2 unsubscribes AFTER u1 accepted, then u2's old accept link is clicked
    _post_prefs(client, app_main, u2.id, "unsubscribe")
    sig2 = app_main.response_service.sign(str(meet.id), u2.id, "accept")
    client.post("/respond", data={"meet_id": str(meet.id), "uid": u2.id,
                                  "action": "accept", "signature": sig2})

    assert app_main.meet_repo.get_by_id(meet.id).status == "connected"
    assert all("connected" not in m["subject"].lower() for m in sent_emails)


# --- footers -----------------------------------------------------------------

def test_match_email_carries_prefs_link(client, app_main, sent_emails, admin_token):
    _user(app_main, "Jane", "jane@example.com")
    _user(app_main, "Ann", "ann@example.com")
    client.post("/admin/matches", headers={"Authorization": f"Bearer {admin_token}"})

    proposals = [m for m in sent_emails if "match this week" in m["subject"]]
    assert proposals
    for m in proposals:
        assert "/preferences?" in m["html"] and "/preferences?" in m["body"]


def test_confirmation_email_carries_prefs_link(client, sent_emails):
    client.post("/join", data={
        "full_name": "Jane", "email": "jane@example.com", "bio": "b",
        "meet_group": "coffee", "gender": "woman", "gender_pref": "any",
        "cadence": "0", "consent": "on",
    })
    assert sent_emails and "/preferences?" in sent_emails[0]["html"]
