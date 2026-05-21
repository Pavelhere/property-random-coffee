# -*- coding: utf-8 -*-

import hashlib
import hmac
from loguru import logger

from models.match_response import MatchResponse
from db.exceptions import MeetNotFoundError, UserNotFoundError

ACTIVITY_LABELS = {
    "coffee": "Coffee chat",
    "walking": "Neighborhood walk",
    "playdate": "Playdate with kids",
}


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

        name1 = user1.full_name or user1.username
        name2 = user2.full_name or user2.username
        activity = ACTIVITY_LABELS.get(user1.meet_group or user2.meet_group, "meetup")
        community = self.community_name

        subject = f"You're connected — {name1} meet {name2} 🎉"

        def _tags_html(extra_info):
            if not extra_info:
                return ""
            tags = [t.strip() for t in extra_info.split(",") if t.strip()]
            if not tags:
                return ""
            return "".join(
                f'<span style="display:inline-block;background:#edf5f0;color:#143c32;'
                f'border-radius:100px;padding:3px 10px;font-size:12px;margin:2px 4px 2px 0">{t}</span>'
                for t in tags[:4]
            )

        def _person_block(name, email, bio, extra_info):
            avatar = name[0].upper() if name else "?"
            tags = _tags_html(extra_info)
            return f"""
<div style="background:#faf7f2;border:1px solid rgba(26,31,24,0.08);border-radius:16px;padding:18px 20px;margin-bottom:16px">
  <div style="display:flex;align-items:flex-start;gap:14px">
    <div style="width:48px;height:48px;border-radius:50%;background:#143c32;color:#f5ede3;
                font-size:18px;font-weight:700;display:flex;align-items:center;justify-content:center;
                flex-shrink:0;text-align:center;line-height:48px;min-width:48px">{avatar}</div>
    <div style="flex:1;min-width:0">
      <div style="font-size:17px;font-weight:700;color:#1a1f18;margin-bottom:4px">{name}</div>
      {'<div style="font-size:14px;color:#5a6356;font-style:italic;margin-bottom:8px;line-height:1.5">"' + bio + '"</div>' if bio else ''}
      {('<div style="margin-bottom:8px">' + tags + '</div>') if tags else ''}
      <div style="font-size:13px;color:#143c32;font-weight:500">📧 {email}</div>
    </div>
  </div>
</div>"""

        html = f"""
<div style="font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;max-width:520px;margin:0 auto;background:#f5ede3;padding:40px 16px">
  <table width="100%" cellpadding="0" cellspacing="0">
    <tr><td align="center" style="padding-bottom:24px">
      <span style="display:inline-block;background:#143c32;color:#f5ede3;font-size:11px;
                   font-weight:700;letter-spacing:2px;text-transform:uppercase;
                   padding:7px 16px;border-radius:100px">{community}</span>
    </td></tr>
    <tr><td style="background:#fff;border-radius:24px;padding:36px 32px;box-shadow:0 4px 24px rgba(20,60,50,0.08)">

      <!-- Headline -->
      <div style="text-align:center;margin-bottom:28px">
        <div style="font-size:28px;margin-bottom:8px">🎉</div>
        <h1 style="font-size:24px;font-weight:700;color:#1a1f18;margin:0 0 8px;letter-spacing:-0.5px">
          You're both in!
        </h1>
        <p style="font-size:15px;color:#5a6356;margin:0;line-height:1.6">
          Both of you said yes to a <strong>{activity.lower()}</strong> at {community}.<br>
          Here's who you're meeting:
        </p>
      </div>

      <!-- Person cards -->
      {_person_block(name1, user1.email, user1.bio, user1.extra_info)}
      <div style="text-align:center;margin:4px 0 12px;font-size:20px;color:#c4a87d">⟷</div>
      {_person_block(name2, user2.email, user2.bio, user2.extra_info)}

      <!-- Next step -->
      <div style="background:#edf5f0;border-radius:14px;padding:16px 20px;margin:24px 0">
        <p style="margin:0;font-size:14px;color:#143c32;font-weight:600;margin-bottom:6px">What to do next</p>
        <p style="margin:0;font-size:14px;color:#2d5a46;line-height:1.6">
          Hit <strong>Reply All</strong> on this email to say hello to each other.
          Suggest a time for a {activity.lower()} — even a hallway hello counts.
        </p>
      </div>

      <p style="font-size:13px;color:#8a9386;text-align:center;margin:0;line-height:1.6">
        Your email addresses are only shared with each other, never posted publicly.
      </p>

    </td></tr>
    <tr><td style="padding-top:24px;text-align:center;font-size:12px;color:#8a9386">
      — Community Coffee
    </td></tr>
  </table>
</div>"""

        plain = (
            f"Hi {name1} and {name2},\n\n"
            f"Great news — you both said yes! Here's how to reach each other:\n\n"
            f"{name1}: {user1.email}\n"
            f"{name2}: {user2.email}\n\n"
            f"Hit Reply All to say hello and set up your {activity.lower()}.\n\n"
            f"— Community Coffee"
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
