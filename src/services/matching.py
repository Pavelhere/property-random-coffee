# -*- coding: utf-8 -*-

import hashlib
import hmac
from urllib.parse import urlencode
from loguru import logger

from utils import season
from models.metadata import Metadata
from db.exceptions import MetadataNotFoundError, UserNotFoundError


class MatchingService:
    METADATA_KEY = "LAST_MATCH_SEASON"

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
        season_id = season.get()

        if not force and not self._should_generate(season_id):
            logger.info("Skipping match generation for season %s (already processed)", season_id)
            return {"status": "skipped", "season": season_id}

        enabled_groups = {group["name"]: group for group in self.config["community"].get("enabledGroups", [])}
        users = list(self.user_repo.list(spec={"pause_in_weeks": "0"}))

        grouped_users = {}
        for user in users:
            if user.meet_group not in enabled_groups:
                continue
            grouped_users.setdefault(user.meet_group, []).append(user)

        for group_name, members in grouped_users.items():
            group_definition = enabled_groups[group_name]
            additional = group_definition.get("additionalUsers", [])
            self.meet_repo.create(
                uids=[user.id for user in members],
                additional_uids=additional
            )

        proposals_sent = self._send_proposals(season_id)
        self._mark_season(season_id)

        return {
            "status": "ok",
            "season": season_id,
            "proposals_sent": proposals_sent
        }

    def _should_generate(self, season_id):
        try:
            metadata = self.metadata_repo.get({"name": self.METADATA_KEY})
            return metadata.value != season_id
        except MetadataNotFoundError:
            return True

    def _mark_season(self, season_id):
        try:
            metadata = self.metadata_repo.get({"name": self.METADATA_KEY})
            metadata.value = season_id
            self.metadata_repo.update(metadata)
        except MetadataNotFoundError:
            self.metadata_repo.add(Metadata(name=self.METADATA_KEY, value=season_id))

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

    ACTIVITY_LABELS = {
        "coffee": "Coffee chat",
        "walking": "Neighborhood walk",
        "playdate": "Playdate with kids",
    }

    def _send_email(self, user, peer, meet):
        accept_url = self._build_action_url(meet.id, user.id, "accept")
        decline_url = self._build_action_url(meet.id, user.id, "decline")
        community_name = self.config["community"].get("displayName", "Community")
        peer_name = peer.full_name or peer.username
        user_name = user.full_name or user.username
        activity_label = self.ACTIVITY_LABELS.get(peer.meet_group, peer.meet_group or "meetup")

        subject = f"Your neighbor match this week — {community_name}"
        body = (
            f"Hi {user_name},\n\n"
            f"This week we paired you with {peer_name}.\n"
        )
        if peer.bio:
            body += f'"{peer.bio}"\n'
        if peer.extra_info:
            body += f"About them: {peer.extra_info}\n"
        body += (
            f"Suggested: {activity_label}\n\n"
            f"Accept: {accept_url}\n"
            f"Decline: {decline_url}\n\n"
            f"— Community Coffee"
        )

        # Build HTML version
        extra_block = ""
        if peer.extra_info:
            tags = [t.strip() for t in peer.extra_info.split(",") if t.strip()]
            if tags:
                tag_html = "".join(
                    f'<span style="display:inline-block;background:#f0ebe3;border-radius:12px;'
                    f'padding:4px 10px;font-size:13px;margin:2px 4px 2px 0">{t}</span>'
                    for t in tags[:4]
                )
                extra_block = f'<div style="margin:12px 0">{tag_html}</div>'

        html = f"""
<div style="font-family:sans-serif;max-width:480px;margin:0 auto;padding:32px 24px;color:#1a1a1a">
  <p style="font-size:13px;letter-spacing:1px;text-transform:uppercase;color:#888;margin:0 0 12px">
    {community_name}
  </p>
  <p style="font-size:16px;color:#444">Hi {user_name},</p>
  <p style="font-size:16px;color:#444;line-height:1.6">
    This week we paired you with a neighbor. Here's who you're meeting:
  </p>
  <div style="border:1px solid #e0d8ce;border-radius:12px;padding:20px;margin:20px 0;background:#faf8f5">
    <h2 style="margin:0 0 6px;font-size:20px">{peer_name}</h2>
    {'<p style="margin:0 0 10px;font-style:italic;color:#555;font-size:14px">"' + peer.bio + '"</p>' if peer.bio else ''}
    {extra_block}
    <p style="margin:8px 0 0;font-size:14px;color:#0d3d3a;font-weight:500">
      ☕ Up for a {activity_label.lower()}
    </p>
  </div>
  <p style="font-size:15px;color:#444">
    Even a hallway hello counts — say yes and we'll share contact details.
  </p>
  <div style="margin:28px 0">
    <a href="{accept_url}"
       style="display:inline-block;background:#0d3d3a;color:#f5ede3;text-decoration:none;
              padding:14px 28px;border-radius:8px;font-size:15px;font-weight:500;margin-right:12px">
      ✓ Accept
    </a>
    <a href="{decline_url}"
       style="display:inline-block;background:#f0ebe3;color:#555;text-decoration:none;
              padding:14px 28px;border-radius:8px;font-size:15px">
      Decline
    </a>
  </div>
  <p style="font-size:13px;color:#aaa">— Community Coffee</p>
</div>
"""

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
