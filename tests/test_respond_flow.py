# -*- coding: utf-8 -*-
"""Meet state machine + /respond confirm-page flow.

The critical properties:
1. GET /respond NEVER changes state (email scanners prefetch GET links).
2. The connection email fires exactly once per meet, ever.
3. connected / declined are terminal — late clicks are no-ops.
"""

import uuid

import pytest

from models.user import User
from models.meet import Meet


def _add_user(app_main, name, email):
    user = User(
        id=str(uuid.uuid4()), username=name, full_name=name, email=email,
        loc="community", meet_group="coffee", pause_in_weeks="0",
        bio=f"{name} bio", extra_info="", gender_pref="any",
    )
    app_main.user_repo.add(user)
    return user


@pytest.fixture()
def meet_setup(app_main):
    u1 = _add_user(app_main, "Jane Kim", "jane@example.com")
    u2 = _add_user(app_main, "Sam Lee", "sam@example.com")
    meet = app_main.meet_repo.add(Meet(season="202627", uid1=u1.id, uid2=u2.id))
    return app_main, u1, u2, meet


def _url(app_main, meet, uid, action):
    sig = app_main.response_service.sign(str(meet.id), uid, action)
    return f"/respond?meet_id={meet.id}&uid={uid}&action={action}&signature={sig}"


def _post(client, app_main, meet, uid, action):
    sig = app_main.response_service.sign(str(meet.id), uid, action)
    return client.post("/respond", data={
        "meet_id": str(meet.id), "uid": uid, "action": action, "signature": sig,
    })


# --- signature validation -------------------------------------------------

def test_tampered_signature_rejected(client, meet_setup):
    app_main, u1, u2, meet = meet_setup
    url = _url(app_main, meet, u1.id, "accept")
    assert client.get(url[:-4] + "beef").status_code == 400
    res = client.post("/respond", data={
        "meet_id": str(meet.id), "uid": u1.id, "action": "accept", "signature": "forged",
    })
    assert res.status_code == 400


def test_signature_for_other_action_rejected(client, meet_setup):
    app_main, u1, u2, meet = meet_setup
    accept_sig = app_main.response_service.sign(str(meet.id), u1.id, "accept")
    res = client.post("/respond", data={
        "meet_id": str(meet.id), "uid": u1.id, "action": "decline", "signature": accept_sig,
    })
    assert res.status_code == 400


def test_uid_not_in_meet_rejected(client, meet_setup, sent_emails):
    app_main, u1, u2, meet = meet_setup
    stranger = _add_user(app_main, "Eve", "eve@example.com")
    res = _post(client, app_main, meet, stranger.id, "accept")
    assert res.status_code == 400
    assert sent_emails == []


# --- GET is read-only (scanner safety) -------------------------------------

def test_get_never_changes_state(client, meet_setup, sent_emails):
    app_main, u1, u2, meet = meet_setup
    # a scanner "clicks" every link in both emails, repeatedly
    for uid in (u1.id, u2.id):
        for action in ("accept", "decline"):
            for _ in range(3):
                assert client.get(_url(app_main, meet, uid, action)).status_code == 200
    fresh = app_main.meet_repo.get_by_id(meet.id)
    assert fresh.status == "pending"
    assert sent_emails == []


def test_get_confirm_page_shows_peer_and_forms(client, meet_setup):
    app_main, u1, u2, meet = meet_setup
    res = client.get(_url(app_main, meet, u1.id, "accept"))
    assert b"Sam" in res.data          # peer first name
    assert b'method="post"' in res.data
    assert res.data.count(b"<form") == 2  # accept + decline


# --- state machine ---------------------------------------------------------

def test_accept_accept_connects_and_emails_once(client, meet_setup, sent_emails):
    app_main, u1, u2, meet = meet_setup
    _post(client, app_main, meet, u1.id, "accept")
    assert app_main.meet_repo.get_by_id(meet.id).status == "pending"
    _post(client, app_main, meet, u2.id, "accept")
    assert app_main.meet_repo.get_by_id(meet.id).status == "connected"

    connection = [m for m in sent_emails if "connected" in m["subject"].lower()
                  or "You're connected" in m["subject"]]
    assert len(connection) == 1
    assert connection[0]["cc"] == "sam@example.com"
    assert "jane@example.com" in connection[0]["body"]


def test_reclick_after_connected_never_resends(client, meet_setup, sent_emails):
    app_main, u1, u2, meet = meet_setup
    _post(client, app_main, meet, u1.id, "accept")
    _post(client, app_main, meet, u2.id, "accept")
    before = len(sent_emails)

    # both residents re-click accept from the old email, several times
    for _ in range(3):
        _post(client, app_main, meet, u1.id, "accept")
        _post(client, app_main, meet, u2.id, "accept")

    assert len(sent_emails) == before
    assert app_main.meet_repo.get_by_id(meet.id).status == "connected"


def test_late_decline_cannot_flip_connected(client, meet_setup):
    app_main, u1, u2, meet = meet_setup
    _post(client, app_main, meet, u1.id, "accept")
    _post(client, app_main, meet, u2.id, "accept")

    res = _post(client, app_main, meet, u1.id, "decline")
    assert res.status_code == 200
    assert app_main.meet_repo.get_by_id(meet.id).status == "connected"


def test_decline_wins_over_pending_accept(client, meet_setup, sent_emails):
    app_main, u1, u2, meet = meet_setup
    _post(client, app_main, meet, u1.id, "accept")
    _post(client, app_main, meet, u2.id, "decline")
    assert app_main.meet_repo.get_by_id(meet.id).status == "declined"

    # a late accept from u2 does not revive the meet
    _post(client, app_main, meet, u2.id, "accept")
    assert app_main.meet_repo.get_by_id(meet.id).status == "declined"
    assert all("connected" not in m["subject"].lower() for m in sent_emails)


def test_get_after_terminal_shows_state_not_buttons(client, meet_setup):
    app_main, u1, u2, meet = meet_setup
    _post(client, app_main, meet, u1.id, "decline")
    res = client.get(_url(app_main, meet, u2.id, "accept"))
    assert res.status_code == 200
    assert b"<form" not in res.data
    assert b"closed" in res.data


def test_xss_bio_escaped_on_confirm_page(client, app_main):
    xss = "<script>alert(1)</script>"
    u1 = _add_user(app_main, "Jane", "j2@example.com")
    u2 = User(
        id=str(uuid.uuid4()), username="Evil", full_name="Evil Person",
        email="evil@example.com", loc="community", meet_group="coffee",
        pause_in_weeks="0", bio=f"hi {xss}", extra_info="", gender_pref="any",
    )
    app_main.user_repo.add(u2)
    meet = app_main.meet_repo.add(Meet(season="202627", uid1=u1.id, uid2=u2.id))
    res = client.get(_url(app_main, meet, u1.id, "accept"))
    assert xss.encode() not in res.data
    assert b"&lt;script&gt;" in res.data
