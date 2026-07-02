# -*- coding: utf-8 -*-
"""MySQL integration tests (run with: pytest -m mysql).

SQLite can lie about exactly the things these paths depend on — unique-index
IntegrityError semantics, DATE/BOOLEAN round-trips, transactional behavior.
These run the same critical paths against the real engine (rcb-mysql-dev
container), in a dedicated coffee_test database that is dropped and
recreated every run.
"""

import uuid
from datetime import date, timedelta

import pytest
from sqlalchemy import create_engine

pytestmark = pytest.mark.mysql

SERVER_URL = "mysql://root:root@127.0.0.1:3308"
TEST_DB = "coffee_test"


@pytest.fixture(scope="module")
def mysql_repos():
    server = create_engine(SERVER_URL)
    try:
        with server.connect() as conn:
            conn.execute(f"DROP DATABASE IF EXISTS {TEST_DB}")
            conn.execute(f"CREATE DATABASE {TEST_DB} CHARACTER SET utf8mb4")
    except Exception as exc:  # container not running
        pytest.skip(f"MySQL not available: {exc}")
    finally:
        server.dispose()

    from db.database import Database
    from db.repo.user import UserRepository
    from db.repo.meet import MeetRepository
    from db.repo.metadata import MetadataRepository
    from db.repo.match_response import MatchResponseRepository
    from db.repo.match_run import MatchRunRepository

    db = Database(f"{SERVER_URL}/{TEST_DB}")
    db.create_database()
    yield {
        "user": UserRepository(session_factory=db.session),
        "meet": MeetRepository(session_factory=db.session),
        "metadata": MetadataRepository(session_factory=db.session),
        "response": MatchResponseRepository(session_factory=db.session),
        "match_run": MatchRunRepository(session_factory=db.session),
    }


class _Outbox:
    def __init__(self):
        self.sent = []

    def send(self, *, to_address, subject, body, html=None, cc_address=None):
        self.sent.append({"to": to_address, "subject": subject, "cc": cc_address})


def _config():
    return {
        "community": {
            "displayName": "Test Ridge",
            "timezone": "America/Chicago",
            "enabledGroups": [{"name": "coffee", "displayName": "Coffee chat", "enabled": True}],
        },
        "app": {"baseUrl": "http://testserver", "responseSecret": "mysql-test-secret"},
    }


def _service(repos, outbox):
    from services.matching import MatchingService
    return MatchingService(
        _config(), repos["user"], repos["meet"], repos["metadata"], outbox,
        match_run_repo=repos["match_run"],
    )


def _add_user(repos, name, **overrides):
    from models.user import User
    fields = dict(
        id=str(uuid.uuid4()), username=name, full_name=name,
        email=f"{name.lower()}@example.com", loc="community",
        meet_group="coffee", pause_in_weeks="0", bio="b", extra_info="",
        gender="woman", gender_pref="any",
    )
    fields.update(overrides)
    user = User(**fields)
    repos["user"].add(user)
    return user


def test_claim_is_atomic_on_real_unique_index(mysql_repos):
    svc = _service(mysql_repos, _Outbox())
    assert svc._claim_run("990001") is True
    assert svc._claim_run("990001") is False  # real MySQL IntegrityError path
    assert svc._claim_run("990002") is True


def test_full_match_cycle_and_refire_safety(mysql_repos):
    outbox = _Outbox()
    svc = _service(mysql_repos, outbox)
    _add_user(mysql_repos, "Jane")
    _add_user(mysql_repos, "Sam", gender="man")

    result = svc.generate_matches()
    assert result["status"] == "ok"
    assert result["proposals_sent"] == 1
    assert len(outbox.sent) == 2  # both sides of the pair

    # cron double-fire on real MySQL
    again = svc.generate_matches()
    assert again["status"] == "skipped"
    assert len(outbox.sent) == 2

    runs = mysql_repos["match_run"].list()
    assert runs and runs[0].proposals_sent == 1


def test_date_and_boolean_roundtrip(mysql_repos):
    user = _add_user(mysql_repos, "Paused")
    user.paused_until = date.today() + timedelta(weeks=2)
    user.unsubscribed = True
    mysql_repos["user"].update(user)

    fresh = mysql_repos["user"].get_by_id(user.id)
    assert fresh.paused_until == date.today() + timedelta(weeks=2)
    assert fresh.unsubscribed is True

    from services.matching import MatchingService
    assert MatchingService._is_active(fresh, date.today()) is False
    fresh.unsubscribed = False
    fresh.paused_until = date.today() - timedelta(days=1)
    mysql_repos["user"].update(fresh)
    fresh2 = mysql_repos["user"].get_by_id(user.id)
    assert MatchingService._is_active(fresh2, date.today()) is True
