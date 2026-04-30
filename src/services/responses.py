# -*- coding: utf-8 -*-

import hashlib
import hmac
from loguru import logger

from models.match_response import MatchResponse
from db.exceptions import MeetNotFoundError


class ResponseService:
    VALID_ACTIONS = {"accept", "decline"}

    def __init__(self, config, meet_repo, response_repo):
        self.meet_repo = meet_repo
        self.response_repo = response_repo
        self.secret = config["app"].get("responseSecret")

        if not self.secret:
            raise ValueError("app.responseSecret is required for response service")

    def validate_signature(self, meet_id, uid, action, provided_signature):
        expected = self._signature(meet_id, uid, action)
        return hmac.compare_digest(expected, provided_signature)

    def record_response(self, meet_id, uid, action):
        if action not in self.VALID_ACTIONS:
            raise ValueError("Unsupported action")

        meet = self.meet_repo.get_by_id(meet_id)
        if uid not in {meet.uid1, meet.uid2}:
            raise ValueError("UID does not belong to the match")

        match_response = MatchResponse(meet_id=meet_id, uid=uid, action=action)
        self.response_repo.add(match_response)

        if action == "accept":
            meet.status = "accepted"
        else:
            meet.status = "declined"

        self.meet_repo.update(meet)
        logger.info("Recorded %s for meet %s by %s", action, meet_id, uid)
        return meet.status

    def _signature(self, meet_id, uid, action):
        data = f"{meet_id}|{uid}|{action}".encode("utf-8")
        return hmac.new(self.secret.encode("utf-8"), data, hashlib.sha256).hexdigest()
