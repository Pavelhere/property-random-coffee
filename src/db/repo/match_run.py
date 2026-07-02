# -*- coding: utf-8 -*-

from contextlib import AbstractContextManager
from typing import Callable, Mapping

from sqlalchemy.orm import Session

from utils import repo
from models.match_run import MatchRun


class MatchRunRepository:
    def __init__(self, session_factory: Callable[..., AbstractContextManager[Session]]) -> None:
        self.session_factory = session_factory

    def add(self, run: MatchRun) -> MatchRun:
        with self.session_factory() as session:
            session.add(run)
            session.commit()
            session.refresh(run)
            return run

    def list(self, spec: Mapping = None) -> list:
        with self.session_factory() as session:
            objs = session.query(MatchRun).order_by(MatchRun.id.desc()).all()
        return repo.filtration(spec, objs)
