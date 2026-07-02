# -*- coding: utf-8 -*-

import hashlib
import hmac
from urllib.parse import urlencode

from loguru import logger
from sqlalchemy.exc import IntegrityError

from utils import config as cfg_utils
from utils import emails, links, season
from models.metadata import Metadata
from db.exceptions import MetadataNotFoundError, UserNotFoundError


class MatchingService:
    """Weekly matching pipeline (triggered by cron via POST /admin/matches).

        cron fires ──► claim run row ──► group active users ──► pair within
        (Mon, prop TZ)  (atomic, unique   by activity          group, avoid
                         MATCH_RUN_{wk})                        repeats
                              │                                    │
                          already ran?                        send proposal
                          → skipped                           emails (signed
                                                              accept/decline)
    """

    def __init__(self, config, user_repo, meet_repo, metadata_repo, email_client):
        self.config = config
        self.user_repo = user_repo
        self.meet_repo = meet_repo
        self.metadata_repo = metadata_repo
        self.email_client = email_client
        self.base_url = config["app"].get("baseUrl", "").rstrip("/")
        self.response_secret = config["app"].get("responseSecret")

        if not self.base_url:
            raise ValueError("app.baseUrl is required for matching service")
        if not self.response_secret:
            raise ValueError("app.responseSecret is required for matching service")

    def generate_matches(self, *, force=False):
        now = cfg_utils.community_now(self.config)
        season_id = season.get(now=now)

        # Atomic claim: inserting the unique MATCH_RUN row either succeeds
        # (we own this week's run) or hits the unique index (someone already
        # ran it). Check-then-act is not enough — double-cron, retries, or
        # two gunicorn workers would race it.
        if not self._claim_run(season_id) and not force:
            logger.info("Skipping match generation for season %s (already processed)", season_id)
            return {"status": "skipped", "season": season_id}

        enabled_groups = {group["name"]: group for group in self.config["community"].get("enabledGroups", [])}
        today = now.date()
        users = [u for u in self.user_repo.list() if self._is_active(u, today)]

        # Pair within (complex, activity): residents of different complexes
        # must never be introduced to each other — separate properties,
        # separate management groups, separate data.
        grouped_users = {}
        for user in users:
            if user.meet_group not in enabled_groups:
                continue
            grouped_users.setdefault((user.loc, user.meet_group), []).append(user)

        considered = []
        for (loc, group_name), members in grouped_users.items():
            group_definition = enabled_groups[group_name]
            additional = group_definition.get("additionalUsers", [])
            self.meet_repo.create(
                uids=[user.id for user in members],
                additional_uids=additional,
                compatible=self._compatibility_checker(members),
                season_id=season_id,
            )
            considered.extend(members)

        unmatched = self._unmatched_users(season_id, considered)
        if unmatched:
            logger.warning(
                "Season %s: %d users unmatched (gender constraints / odd count): %s",
                season_id, len(unmatched), [u.email for u in unmatched],
            )

        proposals_sent = self._send_proposals(season_id)
        self._mark_run_done(season_id)

        return {
            "status": "ok",
            "season": season_id,
            "proposals_sent": proposals_sent,
            "unmatched": [u.email for u in unmatched],
        }

    @staticmethod
    def _is_active(user, today):
        """Matchable = not unsubscribed and not paused into the future."""
        if user.unsubscribed:
            return False
        if user.paused_until and user.paused_until > today:
            return False
        return True

    # gender_pref value → the gender the peer must have for it to be satisfied
    _GENDER_FOR_PREF = {"women": "woman", "men": "man"}

    @classmethod
    def _mutually_compatible(cls, a, b):
        """Both residents' stated preferences must be satisfied.

        "women only"/"men only" are hard constraints: the peer's gender must
        match. "Prefer not to say" (gender unspecified/None) can never satisfy
        a hard constraint, so those residents pair only with "no preference"
        people — best-effort, never stranded by design (they stay eligible
        for the majority of the pool).
        """
        for me, peer in ((a, b), (b, a)):
            required = cls._GENDER_FOR_PREF.get(me.gender_pref)
            if required and peer.gender != required:
                return False
        return True

    def _compatibility_checker(self, members):
        by_id = {u.id: u for u in members}

        def compatible(uid_a, uid_b):
            a, b = by_id.get(uid_a), by_id.get(uid_b)
            if a is None or b is None:
                return True  # additionalUsers outside the group: no data, allow
            return self._mutually_compatible(a, b)

        return compatible

    def _unmatched_users(self, season_id, considered):
        meets = self.meet_repo.list(spec={"season": season_id})
        matched_ids = set()
        for meet in meets:
            matched_ids.add(meet.uid1)
            matched_ids.add(meet.uid2)
        return [u for u in considered if u.id not in matched_ids]

    @staticmethod
    def _run_key(season_id):
        return f"MATCH_RUN_{season_id}"

    def _claim_run(self, season_id):
        """True if this call claimed the week's run; False if already claimed."""
        try:
            self.metadata_repo.add(Metadata(name=self._run_key(season_id), value="running"))
            return True
        except IntegrityError:
            return False

    def _mark_run_done(self, season_id):
        try:
            row = self.metadata_repo.get({"name": self._run_key(season_id)})
            row.value = "done"
            self.metadata_repo.update(row)
        except MetadataNotFoundError:
            # force=True can run without a claim row; nothing to mark
            pass

    def _send_proposals(self, season_id):
        matches = self.meet_repo.list(spec={"season": season_id, "proposal_sent": False})
        sent = 0
        for meet in matches:
            sent_this = self._send_proposal(meet)
            if sent_this:
                sent += 1
        return sent

    def _send_proposal(self, meet):
        try:
            user1 = self.user_repo.get_by_id(meet.uid1)
            user2 = self.user_repo.get_by_id(meet.uid2)
        except UserNotFoundError as exc:
            logger.error("Match %s skipped because user not found: %s", meet.id, exc)
            return False

        if not user1.email or not user2.email:
            logger.warning("Match %s missing email, skipping notification", meet.id)
            return False

        if not self.response_secret:
            logger.error("responseSecret is required to generate response links")
            return False

        sent_both = True
        sent_both &= self._send_email(user1, user2, meet)
        sent_both &= self._send_email(user2, user1, meet)

        if sent_both:
            meet.proposal_sent = True
            self.meet_repo.update(meet)
        return sent_both

    def _send_email(self, user, peer, meet):
        accept_url = self._build_action_url(meet.id, user.id, "accept")
        decline_url = self._build_action_url(meet.id, user.id, "decline")
        community_name = self.config["community"].get("displayName", "Community")

        subject, body, html = emails.match_proposal_email(
            recipient_name=user.full_name or user.username,
            peer_name=peer.full_name or peer.username,
            peer_bio=peer.bio,
            peer_activity=peer.meet_group,
            peer_extra=peer.extra_info,
            accept_url=accept_url,
            decline_url=decline_url,
            community_name=community_name,
            prefs_url=links.preferences_url(self.base_url, self.response_secret, user.id),
        )

        try:
            self.email_client.send(to_address=user.email, subject=subject, body=body, html=html)
            logger.info("Sent match proposal to %s for meet %s", user.email, meet.id)
            return True
        except Exception as exc:
            logger.error("Failed to send email to %s for meet %s: %s", user.email, meet.id, exc)
            return False


    def _build_action_url(self, meet_id, uid, action):
        payload = {
            "meet_id": meet_id,
            "uid": uid,
            "action": action,
            "signature": self._signature(meet_id, uid, action)
        }
        separator = "?" if "?" not in self.base_url else "&"
        return f"{self.base_url}/respond{separator}{urlencode(payload)}"

    def _signature(self, meet_id, uid, action):
        data = f"{meet_id}|{uid}|{action}".encode("utf-8")
        return hmac.new(self.response_secret.encode("utf-8"), data, hashlib.sha256).hexdigest()
