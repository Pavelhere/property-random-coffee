# -*- coding: utf-8 -*-
"""Single source of truth for every email the app sends.

All user-supplied values (names, bios, life-context tags) are HTML-escaped
here, at the point they enter markup. Plain-text bodies and subjects stay
text-only (no markup, nothing to escape beyond being literal text).

Used by: services/matching.py (weekly proposal), services/responses.py
(connection email), main.py (signup confirmation + admin test email — the
test email uses the SAME proposal template as real sends, so the admin
preview can never drift from reality again).
"""

from markupsafe import escape

from constants.common import ACTIVITY_LABELS


def _tags_html(extra_info, bg="#f0ebe3", color="#1a1a1a"):
    """Comma-joined life-context string → escaped pill spans (max 4)."""
    if not extra_info:
        return ""
    tags = [t.strip() for t in extra_info.split(",") if t.strip()]
    if not tags:
        return ""
    return "".join(
        f'<span style="display:inline-block;background:{bg};color:{color};border-radius:12px;'
        f'padding:4px 10px;font-size:13px;margin:2px 4px 2px 0">{escape(t)}</span>'
        for t in tags[:4]
    )


def confirmation_email(name, community_name):
    """Sent immediately after signup."""
    subject = f"You're in — {community_name}"
    body = (
        f"Hi {name},\n\n"
        f"You're registered for {community_name}!\n\n"
        "Every Monday you'll get a personal intro to one neighbor — their name, "
        "a short bio, and a suggested way to meet. One tap to accept.\n\n"
        f"— The {community_name} team"
    )
    html = f"""
<div style="font-family:sans-serif;max-width:480px;margin:0 auto;padding:32px 24px;color:#1a1a1a">
  <p style="font-size:13px;letter-spacing:1px;text-transform:uppercase;color:#888;margin:0 0 12px">
    {escape(community_name)}
  </p>
  <h1 style="font-size:28px;margin:0 0 16px">You're in, {escape(name)}!</h1>
  <p style="font-size:16px;color:#444;line-height:1.6">
    Every Monday you'll receive a personal intro to one neighbor — their name,
    a short bio, and a suggested way to meet. One tap to accept.
  </p>
  <p style="font-size:16px;color:#444;line-height:1.6">
    No app, no account. Just a friendly email once a week.
  </p>
  <p style="font-size:14px;color:#888;margin-top:32px">
    — Community Coffee
  </p>
</div>
"""
    return subject, body, html


def match_proposal_email(*, recipient_name, peer_name, peer_bio, peer_activity,
                         peer_extra, accept_url, decline_url, community_name):
    """Weekly match intro with Accept / Decline links."""
    activity_label = ACTIVITY_LABELS.get(peer_activity, peer_activity or "meetup")

    subject = f"Your neighbor match this week — {community_name}"

    body = (
        f"Hi {recipient_name},\n\n"
        f"This week we paired you with {peer_name}.\n"
    )
    if peer_bio:
        body += f'"{peer_bio}"\n'
    if peer_extra:
        body += f"About them: {peer_extra}\n"
    body += (
        f"Suggested: {activity_label}\n\n"
        f"Accept: {accept_url}\n"
        f"Decline: {decline_url}\n\n"
        f"— Community Coffee"
    )

    tags = _tags_html(peer_extra)
    extra_block = f'<div style="margin:12px 0">{tags}</div>' if tags else ""
    bio_block = (
        f'<p style="margin:0 0 10px;font-style:italic;color:#555;font-size:14px">"{escape(peer_bio)}"</p>'
        if peer_bio else ""
    )

    html = f"""
<div style="font-family:sans-serif;max-width:480px;margin:0 auto;padding:32px 24px;color:#1a1a1a">
  <p style="font-size:13px;letter-spacing:1px;text-transform:uppercase;color:#888;margin:0 0 12px">
    {escape(community_name)}
  </p>
  <p style="font-size:16px;color:#444">Hi {escape(recipient_name)},</p>
  <p style="font-size:16px;color:#444;line-height:1.6">
    This week we paired you with a neighbor. Here's who you're meeting:
  </p>
  <div style="border:1px solid #e0d8ce;border-radius:12px;padding:20px;margin:20px 0;background:#faf8f5">
    <h2 style="margin:0 0 6px;font-size:20px">{escape(peer_name)}</h2>
    {bio_block}
    {extra_block}
    <p style="margin:8px 0 0;font-size:14px;color:#0d3d3a;font-weight:500">
      ☕ Up for a {escape(activity_label.lower())}
    </p>
  </div>
  <p style="font-size:15px;color:#444">
    Even a hallway hello counts — say yes and we'll share contact details.
  </p>
  <div style="margin:28px 0">
    <a href="{escape(accept_url)}"
       style="display:inline-block;background:#0d3d3a;color:#f5ede3;text-decoration:none;
              padding:14px 28px;border-radius:8px;font-size:15px;font-weight:500;margin-right:12px">
      ✓ Accept
    </a>
    <a href="{escape(decline_url)}"
       style="display:inline-block;background:#f0ebe3;color:#555;text-decoration:none;
              padding:14px 28px;border-radius:8px;font-size:15px">
      Decline
    </a>
  </div>
  <p style="font-size:13px;color:#aaa">— Community Coffee</p>
</div>
"""
    return subject, body, html


def _person_block(name, email, bio, extra_info):
    avatar = escape(name[0].upper()) if name else "?"
    tags = _tags_html(extra_info, bg="#edf5f0", color="#143c32")
    bio_block = (
        f'<div style="font-size:14px;color:#5a6356;font-style:italic;margin-bottom:8px;line-height:1.5">"{escape(bio)}"</div>'
        if bio else ""
    )
    tags_block = f'<div style="margin-bottom:8px">{tags}</div>' if tags else ""
    return f"""
<div style="background:#faf7f2;border:1px solid rgba(26,31,24,0.08);border-radius:16px;padding:18px 20px;margin-bottom:16px">
  <div style="display:flex;align-items:flex-start;gap:14px">
    <div style="width:48px;height:48px;border-radius:50%;background:#143c32;color:#f5ede3;
                font-size:18px;font-weight:700;display:flex;align-items:center;justify-content:center;
                flex-shrink:0;text-align:center;line-height:48px;min-width:48px">{avatar}</div>
    <div style="flex:1;min-width:0">
      <div style="font-size:17px;font-weight:700;color:#1a1f18;margin-bottom:4px">{escape(name)}</div>
      {bio_block}
      {tags_block}
      <div style="font-size:13px;color:#143c32;font-weight:500">📧 {escape(email)}</div>
    </div>
  </div>
</div>"""


def connection_email(*, user1, user2, community_name):
    """Both said yes: mutual intro with contact details (send to user1, CC user2)."""
    name1 = user1.full_name or user1.username
    name2 = user2.full_name or user2.username
    activity = ACTIVITY_LABELS.get(user1.meet_group or user2.meet_group, "meetup")

    subject = f"You're connected — {name1} meet {name2} 🎉"

    html = f"""
<div style="font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;max-width:520px;margin:0 auto;background:#f5ede3;padding:40px 16px">
  <table width="100%" cellpadding="0" cellspacing="0">
    <tr><td align="center" style="padding-bottom:24px">
      <span style="display:inline-block;background:#143c32;color:#f5ede3;font-size:11px;
                   font-weight:700;letter-spacing:2px;text-transform:uppercase;
                   padding:7px 16px;border-radius:100px">{escape(community_name)}</span>
    </td></tr>
    <tr><td style="background:#fff;border-radius:24px;padding:36px 32px;box-shadow:0 4px 24px rgba(20,60,50,0.08)">

      <div style="text-align:center;margin-bottom:28px">
        <div style="font-size:28px;margin-bottom:8px">🎉</div>
        <h1 style="font-size:24px;font-weight:700;color:#1a1f18;margin:0 0 8px;letter-spacing:-0.5px">
          You're both in!
        </h1>
        <p style="font-size:15px;color:#5a6356;margin:0;line-height:1.6">
          Both of you said yes to a <strong>{escape(activity.lower())}</strong> at {escape(community_name)}.<br>
          Here's who you're meeting:
        </p>
      </div>

      {_person_block(name1, user1.email, user1.bio, user1.extra_info)}
      <div style="text-align:center;margin:4px 0 12px;font-size:20px;color:#c4a87d">⟷</div>
      {_person_block(name2, user2.email, user2.bio, user2.extra_info)}

      <div style="background:#edf5f0;border-radius:14px;padding:16px 20px;margin:24px 0">
        <p style="margin:0;font-size:14px;color:#143c32;font-weight:600;margin-bottom:6px">What to do next</p>
        <p style="margin:0;font-size:14px;color:#2d5a46;line-height:1.6">
          Hit <strong>Reply All</strong> on this email to say hello to each other.
          Suggest a time for a {escape(activity.lower())} — even a hallway hello counts.
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
    return subject, plain, html
