# -*- coding: utf-8 -*-

from db import database
from db.repo.user import UserRepository
from db.repo.notification import NotificationRepository
from db.repo.rating import RatingRepository
from db.repo.meet import MeetRepository
from db.repo.metadata import MetadataRepository
from db.repo.match_response import MatchResponseRepository

_db_instance = None


def _create_db(config):
    db_url = "mysql://{}:{}@{}:{}/{}".format(
        config["database"]["username"], config["database"]["password"],
        config["database"]["host"], config["database"]["port"],
        config["database"]["db"]
    )
    db = database.Database(db_url)
    db.create_database()
    return db


def get_database(config):
    global _db_instance
    if _db_instance is None:
        _db_instance = _create_db(config)
    return _db_instance


def _build_repos(db):
    user_repo = UserRepository(session_factory=db.session)
    ntf_repo = NotificationRepository(session_factory=db.session)
    rating_repo = RatingRepository(session_factory=db.session)
    meet_repo = MeetRepository(session_factory=db.session)
    metadata_repo = MetadataRepository(session_factory=db.session)
    return user_repo, ntf_repo, rating_repo, meet_repo, metadata_repo


def get_repos(config):
    db = get_database(config)
    return _build_repos(db)


def get_repos_with_responses(config):
    db = get_database(config)
    repos = _build_repos(db)
    match_response_repo = MatchResponseRepository(session_factory=db.session)
    return (*repos, match_response_repo)
