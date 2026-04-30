# -*- coding: utf-8 -*-

from sqlalchemy import Column, Integer, String, ForeignKey, DateTime
from sqlalchemy.sql import func

from db.database import Base
from constants import common


class MatchResponse(Base):
    __tablename__ = common.DB_TABLES.match_response

    id = Column(Integer, primary_key=True, unique=True, nullable=False, autoincrement=True)
    meet_id = Column(Integer, ForeignKey(f"{common.DB_TABLES.meet}.id", ondelete="CASCADE"), nullable=False)
    uid = Column(String(128), nullable=False)
    action = Column(String(32), nullable=False)

    tmst_created = Column(DateTime(timezone=True), server_default=func.now())
    tmst_updated = Column(DateTime(timezone=True), onupdate=func.now())

    def __repr__(self):
        return f'<MatchResponse(id="{self.id}", ' \
               f'meet_id="{self.meet_id}", ' \
               f'uid="{self.uid}", ' \
               f'action="{self.action}")>'
