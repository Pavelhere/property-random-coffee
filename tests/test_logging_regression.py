# -*- coding: utf-8 -*-
# Regression: ISSUE-001 — loguru does not interpolate %s-style args, so every
# email/matching log line printed literal "%s" instead of recipient/subject.
# In dry-run mode those logs are the ONLY visibility into what would be sent.
# Found by /qa on 2026-07-02
# Report: .gstack/qa-reports/qa-report-127-0-0-1-2026-07-02.md

from loguru import logger

from utils.emailer import EmailClient


def _capture(fn):
    records = []
    sink_id = logger.add(lambda msg: records.append(str(msg)), level="DEBUG")
    try:
        fn()
    finally:
        logger.remove(sink_id)
    return "".join(records)


def test_dry_run_email_log_carries_recipient_and_subject():
    client = EmailClient({"email": {}, "resend": {}}, dry_run=True)
    out = _capture(lambda: client.send(
        to_address="resident@example.com",
        subject="Your neighbor match this week — Preston Ridge",
        body="hello",
    ))
    assert "resident@example.com" in out
    assert "Your neighbor match this week" in out
    assert "%s" not in out


def test_dry_run_email_log_carries_cc():
    client = EmailClient({"email": {}, "resend": {}}, dry_run=True)
    out = _capture(lambda: client.send(
        to_address="a@example.com", subject="s", body="b", cc_address="b@example.com",
    ))
    assert "b@example.com" in out


# Regression: ISSUE-002 — every new signup logged "Session rollback because
# of exception" with a full UserNotFoundError traceback. That's the expected
# email-not-found → create path, but repos raised NotFound INSIDE the session
# context manager, which error-logs any exception. NotFound is now raised
# after the session closes.
# Found by /qa on 2026-07-02, fixed 2026-07-03.
# Report: .gstack/qa-reports/qa-report-127-0-0-1-2026-07-02.md

def test_new_signup_logs_no_rollback_traceback(client, sent_emails):
    records = []
    sink_id = logger.add(lambda msg: records.append(str(msg)), level="DEBUG")
    try:
        res = client.post("/join", data={
            "full_name": "Fresh User", "email": "fresh@example.com",
            "bio": "b", "meet_group": "coffee", "gender": "woman",
            "gender_pref": "any", "cadence": "0", "consent": "on",
        })
    finally:
        logger.remove(sink_id)

    out = "".join(records)
    assert res.status_code == 200
    assert len(sent_emails) == 1  # signup still worked end-to-end
    assert "Session rollback" not in out
    assert "UserNotFoundError" not in out
    assert "Traceback" not in out


def test_missing_user_and_meet_lookups_are_quiet(repos):
    from db.exceptions import UserNotFoundError, MeetNotFoundError
    import pytest

    user_repo, meet_repo, _, _, _ = repos
    records = []
    sink_id = logger.add(lambda msg: records.append(str(msg)), level="DEBUG")
    try:
        with pytest.raises(UserNotFoundError):
            user_repo.get_by_id("no-such-uid")
        with pytest.raises(UserNotFoundError):
            user_repo.get_by_email("ghost@example.com")
        with pytest.raises(MeetNotFoundError):
            meet_repo.get_by_id(999999)
    finally:
        logger.remove(sink_id)

    out = "".join(records)
    assert "Session rollback" not in out


def test_no_percent_s_logger_calls_remain_in_src():
    # The whole class of bug: loguru + %s args silently drops the values.
    import pathlib
    import re
    bad = []
    for path in pathlib.Path("src").rglob("*.py"):
        for n, line in enumerate(path.read_text().splitlines(), 1):
            if re.search(r'logger\.\w+\("[^"]*%[sd]', line):
                bad.append(f"{path}:{n}")
    assert bad == [], f"%s-style logger calls (loguru drops the args): {bad}"
