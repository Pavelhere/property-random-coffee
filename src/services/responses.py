# -*- coding: utf-8 -*-

import hashlib
import hmac
from loguru import logger

from models.match_response import MatchResponse
from db.exceptions import MeetNotFoundError, UserNotFoundError
from utils import emails


class ResponseService:
    VALID_ACTIONS = {"accept", "decline"}

    def __init__(self, config, meet_repo, response_repo, user_repo=None, email_client=None):
        self.meet_repo = meet_repo
        self.response_repo = response_repo
        self.user_repo = user_repo
        self.email_client = email_client
        self.secret = config["app"].get("responseSecret")
        self.community_name = config["community"].get("displayName", "Community Coffee")
        self.base_url = config["app"].get("baseUrl", "").rstrip("/")

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

        # Record this response
        match_response = MatchResponse(meet_id=meet_id, uid=uid, action=action)
        self.response_repo.add(match_response)

        # Compute status from ALL responses for this meet (not just current action)
        all_responses = self.response_repo.list(spec={"meet_id": meet_id})
        actions_by_uid = {r.uid: r.action for r in all_responses}

        uid1_action = actions_by_uid.get(meet.uid1)
        uid2_action = actions_by_uid.get(meet.uid2)

        if uid1_action == "accept" and uid2_action == "accept":
            meet.status = "connected"
            self.meet_repo.update(meet)
            logger.info("Both accepted meet %s — sending connection email", meet_id)
            self._send_connection_email(meet)
        elif "decline" in actions_by_uid.values():
            meet.status = "declined"
            self.meet_repo.update(meet)
            logger.info("Meet %s declined", meet_id)
        else:
            meet.status = "pending"
            self.meet_repo.update(meet)
            logger.info("Meet %s pending — waiting for second response", meet_id)

        logger.info("Recorded %s for meet %s by %s", action, meet_id, uid)
        return meet.status

    def get_peer(self, meet, uid):
        """Return the other user in a meet."""
        peer_uid = meet.uid2 if uid == meet.uid1 else meet.uid1
        if self.user_repo:
            try:
                return self.user_repo.get_by_id(peer_uid)
            except UserNotFoundError:
                return None
        return None

    def _send_connection_email(self, meet):
        if not self.email_client or not self.user_repo:
            logger.warning("Cannot send connection email — user_repo or email_client not configured")
            return

        try:
            user1 = self.user_repo.get_by_id(meet.uid1)
            user2 = self.user_repo.get_by_id(meet.uid2)
        except UserNotFoundError as exc:
            logger.error("Cannot send connection email for meet %s: %s", meet.id, exc)
            return

        subject, plain, html = emails.connection_email(
            user1=user1, user2=user2, community_name=self.community_name,
        )

        try:
            # Send to user1, CC user2 so Reply All connects them
            self.email_client.send(
                to_address=user1.email,
                subject=subject,
                body=plain,
                html=html,
                cc_address=user2.email,
            )
            logger.info("Sent connection email for meet %s", meet.id)
        except Exception as exc:
            logger.error("Failed to send connection email for meet %s: %s", meet.id, exc)

    def _signature(self, meet_id, uid, action):
        data = f"{meet_id}|{uid}|{action}".encode("utf-8")
        return hmac.new(self.secret.encode("utf-8"), data, hashlib.sha256).hexdigest()
