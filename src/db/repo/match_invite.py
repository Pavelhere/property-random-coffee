# -*- coding: utf-8 -*-

from contextlib import AbstractContextManager
from typing import Callable, Iterator, Mapping

from sqlalchemy.orm import Session

from utils import repo
from models.match_invite import MatchInvite
from db.exceptions import MatchInviteNotFoundError


class MatchInviteRepository:
    def __init__(self, session_factory: Callable[..., AbstractContextManager[Session]]) -> None:
        self.session_factory = session_factory

    def add(self, invite: MatchInvite) -> MatchInvite:
        with self.session_factory() as session:
            session.add(invite)
            session.commit()
            session.refresh(invite)
            return invite

    def update(self, invite: MatchInvite) -> None:
        with self.session_factory() as session:
            session.query(MatchInvite).filter_by(id=invite.id).update(dict(
                meet_id=invite.meet_id,
                uid=invite.uid,
                token=invite.token,
                status=invite.status
            ))
            session.commit()

    def get_by_token(self, token: str) -> MatchInvite:
        with self.session_factory() as session:
            invite = session.query(MatchInvite).filter(MatchInvite.token == token).first()
            if not invite:
                raise MatchInviteNotFoundError(token)
            return invite

    def get_by_meet_user(self, meet_id: int, uid: str) -> MatchInvite:
        with self.session_factory() as session:
            invite = session.query(MatchInvite).filter(
                MatchInvite.meet_id == meet_id,
                MatchInvite.uid == uid
            ).first()
            if not invite:
                raise MatchInviteNotFoundError(f"{meet_id}:{uid}")
            return invite

    def list(self, spec: Mapping = None) -> Iterator[MatchInvite]:
        with self.session_factory() as session:
            objs = session.query(MatchInvite).all()

        return repo.filtration(spec, objs)
