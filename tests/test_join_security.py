# -*- coding: utf-8 -*-
"""Signup security: no silent overwrite, signed edit links, throttle.

The attack this closes: anyone who knows a resident's email could re-submit
the signup form and rewrite that resident's whole profile (bio, preferences,
pause state). Now the profile only changes through a signed link sent to the
inbox owner.
"""

import time
from urllib.parse import urlparse, parse_qs

from utils import links


def _join(client, email="jane@example.com", **overrides):
    form = {
        "full_name": "Jane Kim", "email": email, "bio": "Baker.",
        "meet_group": "coffee", "gender": "woman", "gender_pref": "any",
        "cadence": "0", "consent": "on",
    }
    form.update(overrides)
    return client.post("/join", data=form)


def _edit_params(uid):
    url = links.edit_url("http://testserver", "test-response-secret", uid)
    return {k: v[0] for k, v in parse_qs(urlparse(url).query).items()}


# --- no silent overwrite -----------------------------------------------------

def test_resignup_does_not_touch_profile(client, app_main, sent_emails):
    _join(client)
    original = app_main.user_repo.get_by_email("jane@example.com")

    # attacker (or Jane herself) re-submits with different data
    res = _join(client, full_name="Hacked Name", bio="pwned bio", gender_pref="men")
    assert res.status_code == 200  # neutral response, same as success

    fresh = app_main.user_repo.get_by_email("jane@example.com")
    assert fresh.full_name == original.full_name == "Jane Kim"
    assert fresh.bio == "Baker."
    assert fresh.gender_pref == "any"


def test_resignup_sends_edit_link_not_confirmation(client, app_main, sent_emails):
    _join(client)
    sent_emails.clear()
    _join(client, bio="new bio attempt")

    assert len(sent_emails) == 1
    assert "Update your profile" in sent_emails[0]["subject"]
    assert "/profile/edit?" in sent_emails[0]["html"]


def test_neutral_json_response_no_enumeration(client, app_main):
    first = client.post("/join", json={
        "full_name": "Jane", "email": "jane@example.com", "bio": "b",
        "meet_group": "coffee", "gender": "woman", "gender_pref": "any",
    })
    second = client.post("/join", json={
        "full_name": "X", "email": "jane@example.com", "bio": "y",
        "meet_group": "coffee", "gender": "man", "gender_pref": "any",
    })
    # identical bodies: an attacker can't tell existing from new emails
    assert first.get_json() == second.get_json()


# --- edit link ---------------------------------------------------------------

def test_edit_link_updates_profile(client, app_main):
    _join(client)
    user = app_main.user_repo.get_by_email("jane@example.com")

    params = _edit_params(user.id)
    res = client.get("/profile/edit", query_string=params)
    assert res.status_code == 200
    assert b"Baker." in res.data  # prefilled

    data = dict(params, full_name="Jane K.", bio="Sourdough now.",
                meet_group="walking", gender="woman", gender_pref="women")
    res = client.post("/profile/edit", data=data)
    assert res.status_code == 200

    fresh = app_main.user_repo.get_by_id(user.id)
    assert fresh.bio == "Sourdough now."
    assert fresh.meet_group == "walking"
    assert fresh.gender_pref == "women"


def test_edit_link_expired_or_forged_rejected(client, app_main):
    _join(client)
    user = app_main.user_repo.get_by_email("jane@example.com")

    params = _edit_params(user.id)
    forged = dict(params, signature="feedface")
    assert client.get("/profile/edit", query_string=forged).status_code == 400

    old_exp = int(time.time()) - 5
    expired_sig = links._sig("test-response-secret", "edit", user.id, old_exp)
    expired = dict(uid=user.id, exp=str(old_exp), signature=expired_sig)
    assert client.get("/profile/edit", query_string=expired).status_code == 400

    # prefs token can't be replayed as an edit token (purpose namespace)
    prefs_url = links.preferences_url("http://x", "test-response-secret", user.id)
    q = {k: v[0] for k, v in parse_qs(urlparse(prefs_url).query).items()}
    assert client.get("/profile/edit", query_string=q).status_code == 400


def test_edit_save_clears_optouts(client, app_main):
    _join(client)
    user = app_main.user_repo.get_by_email("jane@example.com")
    user.unsubscribed = True
    app_main.user_repo.update(user)

    params = _edit_params(user.id)
    client.post("/profile/edit", data=dict(
        params, full_name="Jane", bio="b", meet_group="coffee",
        gender="woman", gender_pref="any"))
    assert app_main.user_repo.get_by_id(user.id).unsubscribed is False


# --- throttle ----------------------------------------------------------------

def test_join_throttled_per_email(client, app_main, sent_emails):
    _join(client)
    _join(client)  # second submit same email: allowed (edit link)
    res = _join(client)  # third within window: throttled
    assert res.status_code == 429
    assert len(sent_emails) == 2  # no third email sent


def test_join_throttled_per_ip(client, app_main, sent_emails):
    for i in range(5):
        assert _join(client, email=f"user{i}@example.com").status_code == 200
    res = _join(client, email="user6@example.com")
    assert res.status_code == 429
    assert len(sent_emails) == 5
