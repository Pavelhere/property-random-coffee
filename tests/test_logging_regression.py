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
