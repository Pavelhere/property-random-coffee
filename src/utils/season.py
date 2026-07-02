# -*- coding: utf-8 -*-
"""Season ids: one season per ISO week, e.g. '202627'.

Uses %G (ISO week-numbering year) with %V — NOT %Y — so the id is correct
around New Year (Dec 29 2025 is ISO week 1 of 2026: '202601', not '202501').

The old implementation computed "N days ago" relative to the current weekday,
so 'last week' meant a different week depending on which day matching ran —
repeat-avoidance silently checked the wrong weeks except on Mondays. These
functions are weekday-independent by construction: every moment inside the
same ISO week yields the same id.
"""

from datetime import datetime, timedelta


def get(now=None):
    """Season id for the week containing `now` (default: server now).

    Pass a timezone-aware `now` (e.g. utils.config.community_now(config))
    so the week boundary is the property's, not the server's.
    """
    moment = now if now is not None else datetime.now()
    return moment.strftime("%G%V")


def weeks_ago(n, now=None):
    """Season id for the week N whole weeks before `now`. Same answer from
    any weekday of the same week."""
    moment = now if now is not None else datetime.now()
    return (moment - timedelta(weeks=n)).strftime("%G%V")
