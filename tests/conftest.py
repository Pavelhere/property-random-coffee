# -*- coding: utf-8 -*-
"""Test fixtures.

Two layers:

- `repos` — function-scoped, SQLite-backed repositories for unit-testing
  services (matching, responses) without Flask or MySQL.
- `client` — Flask test client. `main.py` builds everything at import time
  and would connect to MySQL, so `db.utils.get_repos` is patched BEFORE the
  first import of `main`; the app runs on a session-scoped SQLite file whose
  tables are wiped between tests.

MySQL-marked integration tests (`-m mysql`) use the real rcb-mysql-dev
container instead; see tests/mysql/.
"""

import os
from contextlib import contextmanager

import pytest
from sqlalchemy import create_engine, orm

# Must be set before main.py (and its services) load config.
os.environ.setdefault("RESPONSE_SECRET", "test-response-secret")
os.environ.setdefault("ADMIN_TOKEN", "test-admin-token")
os.environ.setdefault("NOTIFICATIONS_DRY_RUN", "true")
os.environ.setdefault("APP_BASE_URL", "http://testserver")

from db.database import Base  # noqa: E402
from db.repo.user import UserRepository  # noqa: E402
from db.repo.meet import MeetRepository  # noqa: E402
from db.repo.metadata import MetadataRepository  # noqa: E402
from db.repo.match_response import MatchResponseRepository  # noqa: E402
from db.repo.match_run import MatchRunRepository  # noqa: E402


def _make_session_factory(engine):
    factory = orm.scoped_session(
        orm.sessionmaker(autocommit=False, autoflush=False, bind=engine)
    )

    @contextmanager
    def session():
        s = factory()
        try:
            yield s
        except Exception:
            s.rollback()
            raise
        finally:
            s.close()

    return session


def _build_repos(engine):
    sf = _make_session_factory(engine)
    return (
        UserRepository(session_factory=sf),
        MeetRepository(session_factory=sf),
        MetadataRepository(session_factory=sf),
        MatchResponseRepository(session_factory=sf),
        MatchRunRepository(session_factory=sf),
    )


@pytest.fixture()
def repos(tmp_path):
    """Fresh SQLite-backed (user, meet, metadata, match_response, match_run) repos."""
    engine = create_engine(f"sqlite:///{tmp_path / 'unit.db'}")
    Base.metadata.create_all(engine)
    yield _build_repos(engine)
    engine.dispose()


@pytest.fixture(scope="session")
def _app_module(tmp_path_factory):
    """Import main.py exactly once, backed by SQLite instead of MySQL."""
    db_file = tmp_path_factory.mktemp("appdb") / "app.db"
    engine = create_engine(f"sqlite:///{db_file}")
    Base.metadata.create_all(engine)
    app_repos = _build_repos(engine)

    import db.utils as db_utils
    db_utils.get_repos = lambda config: app_repos  # patched pre-import

    import main
    main.app.config["TESTING"] = True
    return main, engine


@pytest.fixture()
def app_main(_app_module):
    """The imported main module, with all tables wiped for this test."""
    main, engine = _app_module
    with engine.begin() as conn:
        for table in reversed(Base.metadata.sorted_tables):
            conn.execute(table.delete())
    main._THROTTLE.clear()
    return main


@pytest.fixture()
def client(app_main):
    return app_main.app.test_client()


@pytest.fixture()
def sent_emails(app_main, monkeypatch):
    """Capture every email the app tries to send during a test."""
    outbox = []

    def _record(*, to_address, subject, body, html=None, cc_address=None):
        outbox.append({
            "to": to_address, "subject": subject, "body": body,
            "html": html, "cc": cc_address,
        })

    monkeypatch.setattr(app_main.email_client, "send", _record)
    return outbox


@pytest.fixture()
def admin_token():
    return os.environ["ADMIN_TOKEN"]
