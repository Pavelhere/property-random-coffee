# -*- coding: utf-8 -*-

from contextlib import AbstractContextManager
from typing import Callable, Iterator, Mapping

from sqlalchemy.orm import Session

from utils import repo
from models.match_response import MatchResponse


class MatchResponseRepository:
    def __init__(self, session_factory: Callable[..., AbstractContextManager[Session]]) -> None:
        self.session_factory = session_factory

    def add(self, response: MatchResponse) -> MatchResponse:
        with self.session_factory() as session:
            session.add(response)
            session.commit()
            session.refresh(response)
            return response

    def list(self, spec: Mapping = None) -> Iterator[MatchResponse]:
        with self.session_factory() as session:
            objs = session.query(MatchResponse).all()
            if not objs:
                return []
        return repo.filtration(spec, objs)
