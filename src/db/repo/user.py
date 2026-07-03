# -*- coding: utf-8 -*-

from contextlib import AbstractContextManager
from typing import Callable, Iterator, Mapping

from sqlalchemy.orm import Session

from utils import repo
from models.user import User
from db.exceptions import UserNotFoundError


class UserRepository:
    def __init__(self, session_factory: Callable[..., AbstractContextManager[Session]]) -> None:
        self.session_factory = session_factory

    def add(self, user: User) -> User:
        with self.session_factory() as session:
            session.add(user)
            session.commit()
            session.refresh(user)
            return user

    def delete_by_id(self, id: str) -> None:
        with self.session_factory() as session:
            entity: User = session.query(User).filter(User.id == id).first()
            if not entity:
                raise UserNotFoundError(id)
            session.delete(entity)
            session.commit()

    def update(self, user: User) -> None:
        with self.session_factory() as session:
            session.query(User).filter_by(id=user.id).update(dict(
                username=user.username,
                full_name=user.full_name,
                email=user.email,
                pause_in_weeks=user.pause_in_weeks,
                paused_until=user.paused_until,
                unsubscribed=user.unsubscribed,
                loc=user.loc,
                meet_group=user.meet_group,
                bio=user.bio,
                extra_info=user.extra_info,
                gender=user.gender,
                gender_pref=user.gender_pref,
            ))

            session.commit()

    # NotFound is raised AFTER the session closes: it's expected control flow
    # (e.g. /join checks email-exists), and the session context manager logs
    # any exception raised inside it as an error with a full traceback.
    def get_by_id(self, id: str) -> User:
        with self.session_factory() as session:
            user = session.query(User).filter(User.id == id).first()
        if not user:
            raise UserNotFoundError(id)
        return user

    def get_by_email(self, email: str) -> User:
        with self.session_factory() as session:
            user = session.query(User).filter(User.email == email).first()
        if not user:
            raise UserNotFoundError(email)
        return user

    def list(self, spec: Mapping = None) -> Iterator[User]:
        with self.session_factory() as session:
            objs = session.query(User).all()

        return repo.filtration(spec, objs)
