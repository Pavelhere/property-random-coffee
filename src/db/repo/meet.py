# -*- coding: utf-8 -*-

import random

from contextlib import AbstractContextManager
from typing import Callable, Iterator, Mapping

from sqlalchemy.orm import Session, aliased

from sqlalchemy import and_, or_
from loguru import logger

from utils import repo, season

from models.meet import Meet
from models.user import User
from db.exceptions import MeetNotFoundError


class MeetRepository:
    def __init__(self, session_factory: Callable[..., AbstractContextManager[Session]]) -> None:
        self.session_factory = session_factory

    def create(self, uids, additional_uids=None, kind='random', compatible=None,
               season_id=None):
        """Create pairs for this season.

        compatible: optional (uid_a, uid_b) -> bool predicate; pairs failing
        it are never created (mutual gender preferences).
        season_id: pass the caller's (property-timezone) season so pairing
        and proposal sending agree on the week.
        """
        logger.info("Starting algorithm to create meets")

        if additional_uids is None:
            additional_uids = []
        if kind == 'random':
            self.__create_random(uids, additional_uids, compatible, season_id)

        logger.info("Algorithm for creating pairs has successfully completed")

    def _have_met(self, uid1, uid2):
        """True if this pair has EVER been matched (any prior week).

        Repeat-avoidance is season-to-date: at ~40 residents, avoiding only
        last week's pair would produce repeats within a month. The fallback
        loop may still allow a repeat when the alternative is leaving both
        residents unmatched.
        """
        with self.session_factory() as session:
            return session.query(Meet).filter(
                or_(
                    and_(Meet.uid1 == uid1, Meet.uid2 == uid2),
                    and_(Meet.uid1 == uid2, Meet.uid2 == uid1),
                )
            ).count() > 0

    def __create_random(self, uids, additional_users, compatible=None, season_id=None):
        season_id = season_id or season.get()

        for_rand_distr = []

        while len(uids) >= 1:
            cur_uid = uids[0]

            if self.is_exist(season_id, {"or": {"uid1": cur_uid, "uid2": cur_uid}}):
                uids.remove(cur_uid)
                continue

            if len(uids) == 1:
                for_rand_distr.append(cur_uid)
                break

            with self.session_factory() as session:
                # take all meets in the current season
                meets = session.query(Meet).filter_by(season=season_id)

            # Take a shuffled list of available users who do not have a meet in the current season
            potential = []
            for uid in uids:
                if uid == cur_uid:
                    continue
                if compatible and not compatible(cur_uid, uid):
                    continue
                take = True
                for meet in meets:
                    if uid in [meet.uid1, meet.uid2]:
                        take = False
                        break
                if take:
                    potential.append(uid)

            random.shuffle(potential)

            # First shuffled candidate this resident has never met. (The old
            # code punted cur_uid to the fallback pool if the FIRST candidate
            # was a repeat, even when fresh candidates existed further down.)
            pair_uid = None
            for candidate in potential:
                if not self._have_met(cur_uid, candidate):
                    pair_uid = candidate
                    break

            if pair_uid is not None:
                self.add(Meet(season=season_id, uid1=cur_uid, uid2=pair_uid))
                uids.remove(pair_uid)
                logger.info(f"Meet created for pair ({cur_uid}, {pair_uid})")
            else:
                logger.info(f"No never-met candidate for {cur_uid}; deferring to fallback pool")
                for_rand_distr.append(cur_uid)
                uids.remove(cur_uid)

        if for_rand_distr:
            while len(for_rand_distr) > 1:
                uid1 = for_rand_distr[0]

                candidates = [uid for uid in for_rand_distr if uid != uid1]
                if compatible:
                    candidates = [uid for uid in candidates if compatible(uid1, uid)]
                if not candidates:
                    logger.info(f"No compatible fallback pair for {uid1}; left unmatched")
                    for_rand_distr.remove(uid1)
                    continue

                uid2 = random.choice(candidates)
                self.add(Meet(season=season_id, uid1=uid1, uid2=uid2))
                for_rand_distr.remove(uid1)
                for_rand_distr.remove(uid2)
                logger.info(f"Meet created for pair ({uid1}, {uid2})")

        if len(for_rand_distr) == 1:
            uid1 = for_rand_distr[0]
            if additional_users:
                uid2 = random.choice(additional_users)
                if uid1 != uid2:
                    logger.info(f"Meet created for pair ({uid1}, {uid2}); Pair has taken from additionalUsers")
                    self.add(Meet(season=season_id, uid1=uid1, uid2=uid2))
                else:
                    logger.debug(
                        f"Meet wasn't created for pair ({uid1}, {uid2}) because uid1 = uid2; Pair has taken from additionalUsers.")

            else:
                logger.info(f"List of additional users is empty. Meet can not be created for user {uid1}")

    def is_exist(self, season, spec: Mapping = None):
        with self.session_factory() as session:
            meets = session.query(Meet).filter(Meet.season == season)
            if not meets:
                raise MeetNotFoundError("")

            if len(repo.filtration(spec, meets)) > 0:
                return True
            else:
                return False

    def add(self, meet: Meet) -> Meet:
        with self.session_factory() as session:
            session.add(meet)
            session.commit()
            session.refresh(meet)
            return meet

    def update(self, meet: Meet) -> None:
        with self.session_factory() as session:
            session.query(Meet).filter_by(id=meet.id).update(dict(
                season=meet.season,
                uid1=meet.uid1,
                uid2=meet.uid2,
                completed=meet.completed,
                status=meet.status,
                proposal_sent=meet.proposal_sent
            ))

            session.commit()

    def get_by_id(self, meet_id: int) -> Meet:
        with self.session_factory() as session:
            meet = session.query(Meet).filter(Meet.id == meet_id).first()
            if not meet:
                raise MeetNotFoundError(meet_id)
            return meet

    def delete(self, meet: Meet) -> None:
        with self.session_factory() as session:
            entity: Meet = session.query(Meet).filter(Meet.id == meet.id).first()
            if not entity:
                raise MeetNotFoundError(meet.id)
            session.delete(entity)
            session.commit()

    def delete_all_by_uid(self, uid: str) -> None:
        with self.session_factory() as session:
            entities: Meet = session.query(Meet).filter(
                or_(Meet.uid1 == uid, Meet.uid2 == uid)
            )

            if not entities:
                raise MeetNotFoundError("")

            for entity in entities:
                session.delete(entity)

            session.commit()

    def list(self, spec: Mapping = None) -> list:
        with self.session_factory() as session:
            objs = session.query(Meet).all()

        return repo.filtration(spec, objs)

    def list_humanreadable(self) -> list:
        with self.session_factory() as session:
            u1 = aliased(User)
            u2 = aliased(User)

            objs = session.query(
                u1.username, u2.username, u1.meet_group, u2.meet_group, Meet.season, Meet.completed
            ).join(
                u1, u1.id == Meet.uid1
            ).join(
                u2, u2.id == Meet.uid2
            ).all()

        return objs
