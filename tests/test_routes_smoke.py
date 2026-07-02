# -*- coding: utf-8 -*-
"""Route smoke tests: signup form paths + admin auth."""


def _join_form(**overrides):
    form = {
        "full_name": "Jane Kim",
        "email": "jane@example.com",
        "bio": "Amateur baker.",
        "meet_group": "coffee",
        "gender_pref": "any",
        "cadence": "0",
        "consent": "on",
        "life_context": ["New here"],
    }
    form.update(overrides)
    return form


def test_home_renders(client):
    res = client.get("/")
    assert res.status_code == 200
    assert b"Coffee chat" in res.data  # enabledGroups made it to the form


def test_join_happy_path_sends_confirmation(client, sent_emails):
    res = client.post("/join", data=_join_form())
    assert res.status_code == 200
    assert len(sent_emails) == 1
    assert sent_emails[0]["to"] == "jane@example.com"
    assert "You're in" in sent_emails[0]["subject"]


def test_join_missing_required_fields_rejected(client, sent_emails):
    res = client.post("/join", data=_join_form(bio=""))
    assert res.status_code == 400
    assert sent_emails == []


def test_join_requires_consent(client, sent_emails):
    form = _join_form()
    del form["consent"]
    res = client.post("/join", data=form)
    assert res.status_code == 400
    assert sent_emails == []


def test_join_invalid_activity_rejected(client):
    res = client.post("/join", data=_join_form(meet_group="skydiving"))
    assert res.status_code == 400


def test_join_xss_bio_never_rendered_raw(client, sent_emails, app_main):
    xss = '<script>alert(1)</script>'
    res = client.post("/join", data=_join_form(bio=f"hi {xss}"))
    assert res.status_code == 200
    # stored, but the confirmation email HTML never carries it raw
    assert all(xss not in (m["html"] or "") for m in sent_emails)


def test_admin_requires_token(client):
    assert client.get("/admin").status_code == 401
    assert client.get("/admin?token=wrong").status_code == 401


def test_admin_with_token(client, admin_token):
    res = client.get(f"/admin?token={admin_token}")
    assert res.status_code == 200
    assert b"Dashboard" in res.data
