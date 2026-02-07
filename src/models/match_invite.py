# -*- coding: utf-8 -*-

from sqlalchemy import Column, Integer, String, ForeignKey, DateTime
from sqlalchemy.sql import func

from db.database import Base
from constants import common


class MatchInvite(Base):
    __tablename__ = common.DB_TABLES.match_invite

    id = Column(Integer, primary_key=True, unique=True, nullable=False, autoincrement=True)
    meet_id = Column(Integer, ForeignKey(f"{common.DB_TABLES.meet}.id", ondelete="CASCADE"), nullable=False)
    uid = Column(String(48), ForeignKey(f"{common.DB_TABLES.user}.id", ondelete="CASCADE"), nullable=False)
    token = Column(String(64), unique=True, nullable=False)
    status = Column(String(16), unique=False, nullable=False, default="pending")

    tmst_created = Column(DateTime(timezone=True), server_default=func.now())
    tmst_updated = Column(DateTime(timezone=True), onupdate=func.now())

    def __repr__(self):
        return f'<MatchInvite(id="{self.id}", ' \
               f'meet_id="{self.meet_id}", ' \
               f'uid="{self.uid}", ' \
               f'token="{self.token}", ' \
               f'status="{self.status}")>'
