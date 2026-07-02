# -*- coding: utf-8 -*-

from db import database
from db.repo.user import UserRepository
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


def get_repos(config):
    """Return (user_repo, meet_repo, metadata_repo, match_response_repo)."""
    db = get_database(config)
    return (
        UserRepository(session_factory=db.session),
        MeetRepository(session_factory=db.session),
        MetadataRepository(session_factory=db.session),
        MatchResponseRepository(session_factory=db.session),
    )
