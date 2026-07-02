# -*- coding: utf-8 -*-

from sqlalchemy import Column, Boolean, Integer, String, DateTime
from sqlalchemy.sql import func

from db.database import Base
from constants import common


class MatchRun(Base):
    """One row per matching run (real or dry) — the audit trail that answers
    'did Monday actually happen, and what did it do?'"""

    __tablename__ = common.DB_TABLES.match_run

    id = Column(Integer, primary_key=True, unique=True, nullable=False, autoincrement=True)
    season = Column(String(24), nullable=False)
    dry_run = Column(Boolean, nullable=False, default=False)
    status = Column(String(24), nullable=False, default="ok")
    pairs_created = Column(Integer, nullable=False, default=0)
    proposals_sent = Column(Integer, nullable=False, default=0)
    # comma-joined emails of residents left unmatched this run
    unmatched = Column(String(2000), nullable=True)

    tmst_created = Column(DateTime(timezone=True), server_default=func.now())

    def __repr__(self):
        return f'<MatchRun(id="{self.id}", season="{self.season}", ' \
               f'dry_run="{self.dry_run}", status="{self.status}", ' \
               f'pairs="{self.pairs_created}", sent="{self.proposals_sent}")>'
