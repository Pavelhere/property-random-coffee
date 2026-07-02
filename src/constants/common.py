# -*- coding: utf-8 -*-

from pydantic.dataclasses import dataclass


@dataclass
class DBTables:
    user: str = 'user'
    meet: str = 'meet'
    meta: str = 'meta'
    match_response: str = 'match_response'


DB_TABLES = DBTables()

# Single source of truth for activity display names (was duplicated across
# main.py, services/matching.py, and services/responses.py).
ACTIVITY_LABELS = {
    "coffee": "Coffee chat",
    "walking": "Neighborhood walk",
    "playdate": "Playdate with kids",
}
