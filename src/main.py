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
HOME_TEMPLATE = """
<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8">
    <title>Community Tenant Matching</title>
  </head>
  <body>
    <h1>Community Tenant Matching</h1>
    <p>Join the weekly tenant matching that introduces neighbors across your community.</p>
    <form method="post" action="/join">
      <label>Full name<br><input type="text" name="full_name" required></label><br>
      <label>Email<br><input type="email" name="email" required></label><br>
      <label>Location<br><input type="text" name="location" placeholder="Building or floor" required></label><br>
      <label>Preferred group<br>
        <select name="meet_group" required>
          {% for group in groups %}
            <option value="{{ group.name }}">{{ group.displayName }}</option>
          {% endfor %}
        </select>
      </label><br>
      <button type="submit">Join the match</button>
    </form>
    <p>Admins can trigger matching or download data under <code>/admin/matches</code> (requires token).</p>
  </body>
</html>
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
        "group": user1.meet_group or user2.meet_group,
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
    return render_template_string(HOME_TEMPLATE, groups=groups)


@app.route("/join", methods=["POST"])
def join():
    payload = request.get_json(silent=True)
    if payload is None:
        payload = request.form

    email = (payload.get("email") or "").strip().lower()
    full_name = (payload.get("full_name") or "").strip()
    meet_group = (payload.get("meet_group") or "").strip()
    location = (payload.get("location") or "").strip() or "community"

    if not email or not full_name or not meet_group:
        return jsonify({"error": "email, full_name, and meet_group are required"}), 400

    permitted_groups = {group["name"] for group in config["community"].get("enabledGroups", [])}
    if meet_group not in permitted_groups:
        return jsonify({"error": "Invalid group"}), 400

    try:
        user = user_repo.get_by_email(email)
        user.full_name = full_name
        user.username = full_name
        user.email = email
        user.meet_group = meet_group
        user.pause_in_weeks = "0"
        user.loc = location
        user_repo.update(user)
        message = "Profile updated"
    except UserNotFoundError:
        user = User(
            id=str(uuid.uuid4()),
            username=full_name,
            email=email,
            full_name=full_name,
            loc=location,
            meet_group=meet_group,
            pause_in_weeks="0"
        )
        user_repo.add(user)
        message = "Profile created"

    return jsonify({"status": "ok", "message": message})


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
