# -*- coding: utf-8 -*-

from pydantic.dataclasses import dataclass


@dataclass
class DBTables:
    user: str = 'user'
    meet: str = 'meet'
    meta: str = 'meta'
    match_response: str = 'match_response'


DB_TABLES = DBTables()
