# -*- coding: utf-8 -*-
"""Complex (property) scoping: residents of different complexes never mix.

The signup link carries the complex id (/?p=preston-ridge → hidden form
field → user.loc). Matching pairs within (complex, activity) only.
"""

import uuid

from models.user import User


def _user(app_main, name, email, loc, meet_group="coffee"):
    user = User(
        id=str(uuid.uuid4()), username=name, full_name=name, email=email,
        loc=loc, meet_group=meet_group, pause_in_weeks="0",
        bio="b", extra_info="", gender="woman", gender_pref="any",
    )
    app_main.user_repo.add(user)
    return user


def _run(client, admin_token):
    return client.post(
        "/admin/matches", headers={"Authorization": f"Bearer {admin_token}"}
    ).get_json()


def test_signup_link_param_stored(client, app_main):
    res = client.get("/?p=preston-ridge")
    assert b'name="property" value="preston-ridge"' in res.data

    client.post("/join", data={
        "full_name": "Jane", "email": "jane@example.com", "bio": "b",
        "meet_group": "coffee", "gender": "woman", "gender_pref": "any",
        "cadence": "0", "consent": "on", "property": "preston-ridge",
    })
    assert app_main.user_repo.get_by_email("jane@example.com").loc == "preston-ridge"


def test_invalid_property_param_sanitized(client, app_main):
    res = client.get("/?p=<script>alert(1)</script>")
    assert b"<script>alert(1)" not in res.data
    assert b'name="property" value="community"' in res.data

    client.post("/join", data={
        "full_name": "X", "email": "x@example.com", "bio": "b",
        "meet_group": "coffee", "gender": "man", "gender_pref": "any",
        "cadence": "0", "consent": "on", "property": "Robert'); DROP--",
    })
    assert app_main.user_repo.get_by_email("x@example.com").loc == "community"


def test_missing_param_defaults_community(client, app_main):
    res = client.get("/")
    assert b'name="property" value="community"' in res.data


def test_cross_complex_users_never_paired(client, app_main, admin_token):
    _user(app_main, "Jane", "jane@example.com", "preston-ridge")
    _user(app_main, "Ann", "ann@example.com", "cary-greens")

    result = _run(client, admin_token)
    assert result["proposals_sent"] == 0
    assert len(app_main.meet_repo.list()) == 0
    assert set(result["unmatched"]) == {"jane@example.com", "ann@example.com"}


def test_same_complex_pairs_fine(client, app_main, admin_token):
    _user(app_main, "Jane", "jane@example.com", "preston-ridge")
    _user(app_main, "Ann", "ann@example.com", "preston-ridge")
    _user(app_main, "Bob", "bob@example.com", "cary-greens")
    _user(app_main, "Tom", "tom@example.com", "cary-greens")

    result = _run(client, admin_token)
    assert result["proposals_sent"] == 2
    for meet in app_main.meet_repo.list():
        u1 = app_main.user_repo.get_by_id(meet.uid1)
        u2 = app_main.user_repo.get_by_id(meet.uid2)
        assert u1.loc == u2.loc
