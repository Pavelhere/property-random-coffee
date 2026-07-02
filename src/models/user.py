# -*- coding: utf-8 -*-

from sqlalchemy import Column, String, DateTime
from sqlalchemy.sql import func

from db.database import Base
from constants import common


class User(Base):
    __tablename__ = common.DB_TABLES.user

    id = Column(String(128), primary_key=True, nullable=False, unique=True)
    username = Column(String(92), nullable=False, unique=False)
    email = Column(String(128), nullable=True, unique=True)
    full_name = Column(String(128), nullable=True, unique=False)
    pause_in_weeks = Column(String(10), nullable=False, unique=False, default="0")
    loc = Column(String(24), nullable=False, unique=False, default="none")
    meet_group = Column(String(24), nullable=False, unique=False, default="remote")
    bio = Column(String(250), nullable=True)
    extra_info = Column(String(500), nullable=True)
    # gender: "woman" | "man" | "unspecified" — what the resident IS.
    # gender_pref: "any" | "women" | "men" — who they're comfortable meeting.
    # Pairing enforces prefs mutually; "unspecified" can only match "any".
    # (migrations/002_user_gender.sql)
    gender = Column(String(12), nullable=True, default="unspecified")
    gender_pref = Column(String(10), nullable=True)

    tmst_created = Column(DateTime(timezone=True), server_default=func.now())
    tmst_updated = Column(DateTime(timezone=True), onupdate=func.now())

    def __repr__(self):
        return f'<User(id="{self.id}", ' \
               f'username="{self.username}", ' \
               f'email="{self.email}", ' \
               f'full_name="{self.full_name}", ' \
               f'pause_in_weeks="{self.pause_in_weeks}", ' \
               f'loc="{self.loc}", ' \
               f'meet_group="{self.meet_group}")>'
