# -*- coding: utf-8 -*-
"""Gender preference enforcement in pairing.

Rules (decision 2026-07-01, eng review):
- "women only" / "men only" are HARD constraints, honored mutually.
- "prefer not to say" (gender=unspecified) can never satisfy a hard
  constraint, so those residents pair only with "no preference" people.
- Constraint-forced no-matches are reported (result.unmatched), not silent.
"""

import uuid

from models.user import User
from services.matching import MatchingService


def _user(app_main, name, email, gender, gender_pref):
    user = User(
        id=str(uuid.uuid4()), username=name, full_name=name, email=email,
        loc="community", meet_group="coffee", pause_in_weeks="0",
        bio=f"{name} bio", extra_info="", gender=gender, gender_pref=gender_pref,
    )
    app_main.user_repo.add(user)
    return user


def _run(client, admin_token):
    return client.post(
        "/admin/matches", headers={"Authorization": f"Bearer {admin_token}"}
    ).get_json()


# --- pure rule -------------------------------------------------------------

class _P:
    def __init__(self, gender, gender_pref):
        self.gender = gender
        self.gender_pref = gender_pref


def test_mutual_compatibility_rule():
    ok = MatchingService._mutually_compatible
    # both no-preference
    assert ok(_P("woman", "any"), _P("man", "any"))
    # one-sided satisfied both ways
    assert ok(_P("woman", "women"), _P("woman", "any"))
    assert not ok(_P("woman", "women"), _P("man", "any"))
    # must be mutual
    assert ok(_P("man", "women"), _P("woman", "men"))
    assert not ok(_P("man", "women"), _P("woman", "women"))
    # unspecified never satisfies a hard constraint...
    assert not ok(_P("unspecified", "any"), _P("woman", "women"))
    assert not ok(_P(None, "any"), _P("woman", "women"))
    # ...but pairs fine with no-preference
    assert ok(_P("unspecified", "any"), _P("man", "any"))


# --- end-to-end through the match run ---------------------------------------

def test_women_only_never_paired_with_man(client, app_main, sent_emails, admin_token):
    w = _user(app_main, "Jane", "jane@example.com", "woman", "women")
    m = _user(app_main, "Sam", "sam@example.com", "man", "any")

    result = _run(client, admin_token)
    assert result["proposals_sent"] == 0
    assert set(result["unmatched"]) == {"jane@example.com", "sam@example.com"}
    assert len(app_main.meet_repo.list()) == 0
    assert all("match this week" not in e["subject"] for e in sent_emails)


def test_women_only_paired_with_woman(client, app_main, admin_token):
    _user(app_main, "Jane", "jane@example.com", "woman", "women")
    _user(app_main, "Ann", "ann@example.com", "woman", "any")

    result = _run(client, admin_token)
    assert result["proposals_sent"] == 1
    assert result["unmatched"] == []


def test_unspecified_only_pairs_with_no_preference(client, app_main, admin_token):
    _user(app_main, "Pat", "pat@example.com", "unspecified", "any")
    _user(app_main, "Jane", "jane@example.com", "woman", "women")
    result = _run(client, admin_token)
    assert result["proposals_sent"] == 0
    assert set(result["unmatched"]) == {"pat@example.com", "jane@example.com"}


def test_unspecified_pairs_with_any(client, app_main, admin_token):
    _user(app_main, "Pat", "pat@example.com", "unspecified", "any")
    _user(app_main, "Sam", "sam@example.com", "man", "any")
    result = _run(client, admin_token)
    assert result["proposals_sent"] == 1
    assert result["unmatched"] == []


def test_constraints_respected_in_fallback_distribution(client, app_main, admin_token):
    # Three no-preference users + one women-only woman with no compatible
    # candidate: whatever the shuffle does, the women-only resident must
    # never end up with a man.
    _user(app_main, "Jane", "jane@example.com", "woman", "women")
    _user(app_main, "Sam", "sam@example.com", "man", "any")
    _user(app_main, "Tom", "tom@example.com", "man", "any")
    _user(app_main, "Ben", "ben@example.com", "man", "any")

    result = _run(client, admin_token)
    for meet in app_main.meet_repo.list():
        pair = {meet.uid1, meet.uid2}
        users = [app_main.user_repo.get_by_id(uid) for uid in pair]
        genders = {u.gender for u in users}
        prefs = {u.gender_pref for u in users}
        if "women" in prefs:
            assert genders == {"woman"}
    assert "jane@example.com" in result["unmatched"]


def test_join_form_stores_gender(client, app_main, sent_emails):
    res = client.post("/join", data={
        "full_name": "Jane Kim", "email": "jane@example.com",
        "bio": "Baker.", "meet_group": "coffee",
        "gender": "woman", "gender_pref": "women",
        "cadence": "0", "consent": "on",
    })
    assert res.status_code == 200
    user = app_main.user_repo.get_by_email("jane@example.com")
    assert user.gender == "woman"
    assert user.gender_pref == "women"


def test_join_invalid_gender_defaults_unspecified(client, app_main):
    client.post("/join", data={
        "full_name": "X", "email": "x@example.com", "bio": "b",
        "meet_group": "coffee", "gender": "attack-helicopter",
        "gender_pref": "any", "cadence": "0", "consent": "on",
    })
    assert app_main.user_repo.get_by_email("x@example.com").gender == "unspecified"
