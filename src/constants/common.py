# -*- coding: utf-8 -*-

from pydantic.dataclasses import dataclass


@dataclass
class NotificationTypes:
    info: str = 'info'
    looking: str = 'looking'
    reminder: str = 'reminder'
    feedback: str = 'feedback'
    next_week: str = 'next_week'
    match_proposal: str = 'match_proposal'


@dataclass
class DBTables:
    user: str = 'user'
    meet: str = 'meet'
    meta: str = 'meta'
    rating: str = 'rating'
    notification: str = 'notification'
    match_invite: str = 'match_invite'


NTF_TYPES = NotificationTypes()
DB_TABLES = DBTables()
