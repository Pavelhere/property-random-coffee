# -*- coding: utf-8 -*-

import os
import uuid
import csv
import io
from multiprocessing import Process

from flask import Flask, request, jsonify, Response, render_template_string
from loguru import logger

from utils import config as cfg_utils
from db import utils as db_utils
from utils.emailer import EmailClient
from services.matching import MatchingService
from services.responses import ResponseService
from daemons import match_daemon
from models.user import User
from db.exceptions import UserNotFoundError

CONFIG_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "../resources/config.yml"))
config = cfg_utils.load(CONFIG_PATH)
user_repo, _, _, meet_repo, metadata_repo, match_response_repo = db_utils.get_repos_with_responses(config)

email_client = EmailClient(config, dry_run=config["notifications"].get("dryRun", True))
matching_service = MatchingService(config, user_repo, meet_repo, metadata_repo, email_client)
response_service = ResponseService(config, meet_repo, match_response_repo)

app = Flask(__name__)
app.config["ADMIN_TOKEN"] = config["app"].get("adminToken")

ACTIVITY_LABELS = {
    "coffee": "Coffee chat",
    "walking": "Neighborhood walk",
    "playdate": "Playdate with kids",
}

LIFE_CONTEXT_OPTIONS = ["New here", "Works from home", "Has kids", "Pet owner"]

HOME_TEMPLATE = """
<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>{{ community_name }}</title>
  </head>
  <body>
    <h1>{{ community_name }}</h1>
    <p>Join the weekly neighbor matching. Every Monday you'll get a personal intro to one neighbor. No app needed.</p>
    {% if error %}
    <p style="color:red">{{ error }}</p>
    {% endif %}
    <form method="post" action="/join">

      <div>
        <label>Name or nickname *<br>
          <input type="text" name="full_name" required placeholder="How should we introduce you?">
        </label>
      </div>

      <div>
        <label>Email *<br>
          <input type="email" name="email" required placeholder="your@email.com">
        </label>
        <small>Your email is private — it's never shown to neighbors.</small>
      </div>

      <div>
        <label>Short bio * <small>(max 250 characters)</small><br>
          <textarea name="bio" required maxlength="250" rows="3"
                    placeholder="E.g. Product designer, amateur baker, always up for a ramen recommendation."
                    oninput="document.getElementById('bio-count').textContent = 250 - this.value.length"></textarea>
        </label>
        <small><span id="bio-count">250</span> characters remaining</small>
      </div>

      <div>
        <p>Life context (optional — check all that apply)</p>
        {% for tag in life_context_options %}
        <label>
          <input type="checkbox" name="life_context" value="{{ tag }}"> {{ tag }}
        </label><br>
        {% endfor %}
      </div>

      <div>
        <p>Preferred way to meet *</p>
        {% for group in groups %}
        <label>
          <input type="radio" name="meet_group" value="{{ group.name }}" required> {{ group.displayName }}
        </label><br>
        {% endfor %}
      </div>

      <div>
        <p>Who are you comfortable meeting? *</p>
        <label><input type="radio" name="gender_pref" value="any" required checked> No preference</label><br>
        <label><input type="radio" name="gender_pref" value="women"> Women only</label><br>
        <label><input type="radio" name="gender_pref" value="men"> Men only</label><br>
      </div>

      <div>
        <label>
          <input type="checkbox" name="consent" required>
          I agree to receive weekly Community Coffee introduction emails.
        </label>
      </div>

      <input type="hidden" name="cadence" value="0">
      <button type="submit">Join the next Monday match →</button>
    </form>
  </body>
</html>
"""

THANK_YOU_TEMPLATE = """
<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8">
    <title>You're in!</title>
  </head>
  <body>
    <h1>You're in! 🎉</h1>
    <p>Every Monday you'll get a personal intro to one neighbor at {{ community_name }}.</p>
    <p>Check your inbox — we just sent you a confirmation.</p>
  </body>
</html>
"""

ADMIN_TEMPLATE = """
<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8">
    <title>Admin — Community Coffee</title>
  </head>
  <body>
    <h1>Admin Panel</h1>

    <h2>Participants ({{ users|length }})</h2>
    <table border="1" cellpadding="6">
      <thead>
        <tr><th>Name</th><th>Email</th><th>Activity</th><th>Gender pref</th><th>Bio</th><th>Life context</th><th>Cadence</th><th>Joined</th></tr>
      </thead>
      <tbody>
        {% for u in users %}
        <tr>
          <td>{{ u.full_name or u.username }}</td>
          <td>{{ u.email }}</td>
          <td>{{ activity_labels.get(u.meet_group, u.meet_group) }}</td>
          <td>{{ u.gender_pref or '—' }}</td>
          <td>{{ u.bio or '—' }}</td>
          <td>{{ u.extra_info or '—' }}</td>
          <td>{{ 'Weekly' if u.pause_in_weeks == '0' else 'Paused ' + u.pause_in_weeks + 'w' }}</td>
          <td>{{ u.tmst_created.strftime('%Y-%m-%d') if u.tmst_created else '—' }}</td>
        </tr>
        {% endfor %}
      </tbody>
    </table>

    <h2>Actions</h2>
    <form method="post" action="/admin/matches?token={{ token }}">
      <button type="submit">Run matching now</button>
    </form>
    <br>
    <a href="/admin/matches?token={{ token }}&format=csv">Download matches CSV</a>
    <br><br>

    <h2>Test Email</h2>
    <p>Send a sample match email so you can see exactly what residents will receive.</p>
    <form method="get" action="/admin/test-email">
      <input type="hidden" name="token" value="{{ token }}">
      <label>Send to:<br>
        <input type="email" name="to" required placeholder="your@email.com" style="width:260px">
      </label><br><br>
      <button type="submit">Send test match email</button>
    </form>

    {% if message %}
    <p><strong>{{ message }}</strong></p>
    {% endif %}
  </body>
</html>
"""


def _confirmation_email_html(name, community_name):
    return f"""
<div style="font-family:sans-serif;max-width:480px;margin:0 auto;padding:32px 24px;color:#1a1a1a">
  <p style="font-size:13px;letter-spacing:1px;text-transform:uppercase;color:#888;margin:0 0 12px">
    {community_name}
  </p>
  <h1 style="font-size:28px;margin:0 0 16px">You're in, {name}!</h1>
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


def _match_email_html(recipient_name, peer_name, peer_bio, peer_activity, peer_extra,
                      accept_url, decline_url, community_name):
    activity_label = ACTIVITY_LABELS.get(peer_activity, peer_activity)
    extra_block = ""
    if peer_extra:
        tags = [t.strip() for t in peer_extra.split(",") if t.strip()]
        if tags:
            tag_html = "".join(
                f'<span style="display:inline-block;background:#f0ebe3;border-radius:12px;'
                f'padding:4px 10px;font-size:13px;margin:2px 4px 2px 0">{t}</span>'
                for t in tags[:4]
            )
            extra_block = f'<div style="margin:12px 0">{tag_html}</div>'

    return f"""
<div style="font-family:sans-serif;max-width:480px;margin:0 auto;padding:32px 24px;color:#1a1a1a">
  <p style="font-size:13px;letter-spacing:1px;text-transform:uppercase;color:#888;margin:0 0 12px">
    {community_name}
  </p>
  <p style="font-size:16px;color:#444">Hi {recipient_name},</p>
  <p style="font-size:16px;color:#444;line-height:1.6">
    This week we paired you with a neighbor. Here's who you're meeting:
  </p>

  <div style="border:1px solid #e0d8ce;border-radius:12px;padding:20px;margin:20px 0;background:#faf8f5">
    <h2 style="margin:0 0 6px;font-size:20px">{peer_name}</h2>
    <p style="margin:0 0 10px;font-style:italic;color:#555;font-size:14px">"{peer_bio}"</p>
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

  <p style="font-size:13px;color:#aaa">
    — Community Coffee
  </p>
</div>
"""


def _matches_to_csv(rows):
    if not rows:
        return ""
    headers = rows[0].keys()
    out = io.StringIO()
    writer = csv.DictWriter(out, fieldnames=headers)
    writer.writeheader()
    for row in rows:
        writer.writerow(row)
    return out.getvalue()


def _serialize_match(meet):
    try:
        user1 = user_repo.get_by_id(meet.uid1)
        user2 = user_repo.get_by_id(meet.uid2)
    except UserNotFoundError:
        return None

    return {
        "meet_id": meet.id,
        "season": meet.season,
        "status": meet.status,
        "proposal_sent": meet.proposal_sent,
        "uid1": user1.id,
        "email1": user1.email,
        "name1": user1.full_name or user1.username,
        "uid2": user2.id,
        "email2": user2.email,
        "name2": user2.full_name or user2.username,
        "activity": user1.meet_group or user2.meet_group,
    }


def _check_admin():
    token = request.headers.get("Authorization", "")
    if token.startswith("Bearer "):
        token = token.split(" ", 1)[1]
    if not token:
        token = request.args.get("token", "")
    admin_token = app.config.get("ADMIN_TOKEN")
    return bool(admin_token and token == admin_token)


@app.route("/", methods=["GET"])
def home():
    groups = config["community"].get("enabledGroups", [])
    community_name = config["community"].get("displayName", "Community")
    return render_template_string(
        HOME_TEMPLATE,
        groups=groups,
        community_name=community_name,
        life_context_options=LIFE_CONTEXT_OPTIONS,
        error=None,
    )


@app.route("/join", methods=["POST"])
def join():
    payload = request.get_json(silent=True)
    if payload is None:
        payload = request.form

    email = (payload.get("email") or "").strip().lower()
    full_name = (payload.get("full_name") or "").strip()
    meet_group = (payload.get("meet_group") or "").strip()
    bio = (payload.get("bio") or "").strip()[:250]
    gender_pref = (payload.get("gender_pref") or "any").strip()
    cadence = (payload.get("cadence") or "0").strip()
    if cadence not in ("0", "1", "2", "3", "4"):
        cadence = "0"
    if gender_pref not in ("any", "women", "men"):
        gender_pref = "any"

    # Life context: checkboxes → comma-joined string
    if request.is_json:
        life_context_raw = payload.get("life_context", [])
        if isinstance(life_context_raw, str):
            life_context_raw = [life_context_raw]
    else:
        life_context_raw = request.form.getlist("life_context")
    extra_info = ", ".join(
        tag for tag in life_context_raw if tag in LIFE_CONTEXT_OPTIONS
    )

    def _form_error(msg):
        groups = config["community"].get("enabledGroups", [])
        community_name = config["community"].get("displayName", "Community")
        return render_template_string(
            HOME_TEMPLATE, groups=groups, community_name=community_name,
            life_context_options=LIFE_CONTEXT_OPTIONS, error=msg,
        ), 400

    if not email or not full_name or not meet_group or not bio:
        if request.is_json:
            return jsonify({"error": "email, full_name, meet_group, and bio are required"}), 400
        return _form_error("Please fill in all required fields.")

    permitted_groups = {group["name"] for group in config["community"].get("enabledGroups", [])}
    if meet_group not in permitted_groups:
        if request.is_json:
            return jsonify({"error": "Invalid activity preference"}), 400
        return _form_error("Please select a valid activity preference.")

    if not request.is_json and not payload.get("consent"):
        return _form_error("Please agree to receive match emails to continue.")

    try:
        user = user_repo.get_by_email(email)
        user.full_name = full_name
        user.username = full_name
        user.email = email
        user.meet_group = meet_group
        user.pause_in_weeks = cadence
        user.bio = bio
        user.extra_info = extra_info
        user.gender_pref = gender_pref
        user_repo.update(user)
        created = False
    except UserNotFoundError:
        user = User(
            id=str(uuid.uuid4()),
            username=full_name,
            email=email,
            full_name=full_name,
            loc="community",
            meet_group=meet_group,
            pause_in_weeks=cadence,
            bio=bio,
            extra_info=extra_info,
            gender_pref=gender_pref,
        )
        user_repo.add(user)
        created = True

    # Send confirmation email
    community_name = config["community"].get("displayName", "Community")
    try:
        email_client.send(
            to_address=email,
            subject=f"You're in — {community_name}",
            body=(
                f"Hi {full_name},\n\n"
                f"You're registered for {community_name}!\n\n"
                "Every Monday you'll get a personal intro to one neighbor — their name, "
                "a short bio, and a suggested way to meet. One tap to accept.\n\n"
                f"— The {community_name} team"
            ),
            html=_confirmation_email_html(full_name, community_name),
        )
    except Exception as exc:
        logger.error("Failed to send confirmation email to %s: %s", email, exc)

    if request.is_json:
        return jsonify({"status": "ok", "message": "Profile created" if created else "Profile updated"})

    return render_template_string(THANK_YOU_TEMPLATE, community_name=community_name)


@app.route("/admin", methods=["GET"])
def admin_panel():
    if not _check_admin():
        return Response("Unauthorized", status=401)
    token = request.args.get("token", "")
    message = request.args.get("message", "")
    users = list(user_repo.list())
    community_name = config["community"].get("displayName", "Community")
    return render_template_string(
        ADMIN_TEMPLATE,
        users=users,
        token=token,
        message=message,
        activity_labels=ACTIVITY_LABELS,
        community_name=community_name,
    )


@app.route("/admin/test-email", methods=["GET"])
def admin_test_email():
    if not _check_admin():
        return Response("Unauthorized", status=401)

    to = request.args.get("to", "").strip()
    token = request.args.get("token", "")
    if not to:
        return Response("Missing ?to= parameter", status=400)

    community_name = config["community"].get("displayName", "Community")
    base_url = config["app"].get("baseUrl", "http://localhost:5000").rstrip("/")

    html = _match_email_html(
        recipient_name="Alex",
        peer_name="Marcus Lee",
        peer_bio="Product designer, amateur baker, always up for a ramen recommendation.",
        peer_activity="coffee",
        peer_extra="Has kids, Works from home, New here",
        accept_url=f"{base_url}/respond?meet_id=1&uid=test&action=accept&signature=test",
        decline_url=f"{base_url}/respond?meet_id=1&uid=test&action=decline&signature=test",
        community_name=community_name,
    )
    body = (
        f"Hi Alex,\n\n"
        f"This week we paired you with Marcus Lee.\n"
        f"Bio: Product designer, amateur baker, always up for a ramen recommendation.\n"
        f"Suggested: Coffee chat\n\n"
        "This is a TEST email — real links will work when matching runs.\n\n"
        f"— {community_name}"
    )

    try:
        email_client.send(
            to_address=to,
            subject=f"[TEST] Your neighbor match — {community_name}",
            body=body,
            html=html,
        )
        logger.info("Test email sent to %s", to)
        message = f"Test email sent to {to}!"
    except Exception as exc:
        logger.error("Failed to send test email to %s: %s", to, exc)
        message = f"Failed to send: {exc}"

    return render_template_string(
        ADMIN_TEMPLATE,
        users=list(user_repo.list()),
        token=token,
        message=message,
        activity_labels=ACTIVITY_LABELS,
        community_name=community_name,
    )


@app.route("/admin/matches", methods=["GET"])
def list_matches():
    if not _check_admin():
        return jsonify({"error": "Unauthorized"}), 401

    matches = [row for row in (_serialize_match(meet) for meet in meet_repo.list()) if row]
    if request.args.get("format") == "csv":
        csv_data = _matches_to_csv(matches)
        return Response(
            csv_data,
            mimetype="text/csv",
            headers={"Content-Disposition": "attachment; filename=matches.csv"}
        )

    return jsonify(matches)


@app.route("/admin/matches", methods=["POST"])
def trigger_matches():
    if not _check_admin():
        return jsonify({"error": "Unauthorized"}), 401

    force = request.args.get("force", "0").lower() in ("1", "true", "yes")
    result = matching_service.generate_matches(force=force)
    return jsonify(result)


@app.route("/respond", methods=["GET"])
def respond():
    meet_id = request.args.get("meet_id")
    uid = request.args.get("uid")
    action = request.args.get("action")
    signature = request.args.get("signature")

    if not all([meet_id, uid, action, signature]):
        return Response("Missing required parameters", status=400)

    try:
        meet_id_int = int(meet_id)
    except ValueError:
        return Response("Invalid meet_id", status=400)

    if not response_service.validate_signature(meet_id, uid, action, signature):
        return Response("Invalid token", status=400)

    try:
        status = response_service.record_response(meet_id_int, uid, action)
    except Exception as exc:
        logger.error("Failed to store response: %s", exc)
        return Response("Unable to record response", status=400)

    return Response(f"Thank you. Match status is now {status}", status=200)


def _run_match_daemon():
    match_process = Process(
        target=match_daemon.care,
        args=(config, user_repo, meet_repo, metadata_repo, email_client),
        daemon=True
    )
    match_process.start()
    return match_process


if __name__ == "__main__":
    log_dir = os.getenv("RCB_LOG_DIR", os.path.abspath(os.path.join(os.path.dirname(__file__), "../logs")))
    os.makedirs(log_dir, exist_ok=True)
    logger.add(
        os.path.join(log_dir, "match_{time}.log"),
        level="INFO",
        rotation=config["log"]["rotation"],
        compression="zip"
    )

    if not config["app"].get("adminToken"):
        logger.warning("adminToken is not configured; admin routes will be disabled")

    _run_match_daemon()
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
