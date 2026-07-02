# -*- coding: utf-8 -*-
"""Season math (regression) + season-to-date repeat avoidance.

The old season.get('delta', N) computed a different target week depending on
the weekday it ran — repeat-avoidance checked the wrong weeks except on
Mondays. And %Y%V mixed calendar year with ISO week, breaking at New Year.
"""

import uuid
from datetime import datetime, timedelta

from models.user import User
from models.meet import Meet
from utils import season


# --- season ids --------------------------------------------------------------

def test_same_week_same_id_every_weekday():
    # ISO week 27 of 2026: Mon Jun 29 .. Sun Jul 5
    monday = datetime(2026, 6, 29)
    ids = {season.get(now=monday + timedelta(days=d)) for d in range(7)}
    assert ids == {"202627"}


def test_weeks_ago_is_weekday_independent():
    # computed from Monday and from Friday of the same week → same answer
    monday = datetime(2026, 6, 29)
    friday = datetime(2026, 7, 3)
    assert season.weeks_ago(1, now=monday) == season.weeks_ago(1, now=friday) == "202626"
    assert season.weeks_ago(2, now=friday) == "202625"


def test_iso_year_boundary():
    # Dec 29 2025 is a Monday in ISO week 1 of 2026 (%Y would say 2025)
    assert season.get(now=datetime(2025, 12, 29)) == "202601"
    # Jan 1 2027 is a Friday in ISO week 53 of 2026
    assert season.get(now=datetime(2027, 1, 1)) == "202653"
    # weeks_ago crosses the boundary correctly
    assert season.weeks_ago(1, now=datetime(2026, 1, 7)) == "202601"


# --- repeat avoidance ---------------------------------------------------------

def _user(app_main, name):
    user = User(
        id=str(uuid.uuid4()), username=name, full_name=name,
        email=f"{name.lower()}@example.com", loc="community",
        meet_group="coffee", pause_in_weeks="0", bio="b", extra_info="",
        gender="woman", gender_pref="any",
    )
    app_main.user_repo.add(user)
    return user


def test_prior_pair_never_repeated_when_alternatives_exist(app_main):
    a, b, c, d = (_user(app_main, n) for n in ("A", "B", "C", "D"))
    # A and B met in an earlier week
    app_main.meet_repo.add(Meet(season="202601", uid1=a.id, uid2=b.id))

    # While never-met alternatives exist (2 more weeks before this 4-person
    # pool is exhausted), A-B must never re-pair, whatever the shuffle does.
    for i in range(2):
        this_season = f"29900{i}"
        app_main.meet_repo.create(
            uids=[a.id, b.id, c.id, d.id], season_id=this_season)
        pairs = [{m.uid1, m.uid2} for m in app_main.meet_repo.list(
            spec={"season": this_season})]
        assert {a.id, b.id} not in pairs
        assert len(pairs) == 2  # everyone still matched


def test_fallback_allows_repeat_over_stranding(app_main):
    a, b = _user(app_main, "A"), _user(app_main, "B")
    app_main.meet_repo.add(Meet(season="202601", uid1=a.id, uid2=b.id))

    # only two residents, and they've met: a repeat beats no match at all
    app_main.meet_repo.create(uids=[a.id, b.id], season_id="299100")
    pairs = app_main.meet_repo.list(spec={"season": "299100"})
    assert len(pairs) == 1
    assert {pairs[0].uid1, pairs[0].uid2} == {a.id, b.id}


def test_repeat_check_is_symmetric(app_main):
    a, b = _user(app_main, "A"), _user(app_main, "B")
    app_main.meet_repo.add(Meet(season="202601", uid1=a.id, uid2=b.id))
    assert app_main.meet_repo._have_met(a.id, b.id) is True
    assert app_main.meet_repo._have_met(b.id, a.id) is True
    c = _user(app_main, "C")
    assert app_main.meet_repo._have_met(a.id, c.id) is False
