# -*- coding: utf-8 -*-

import csv
import io
import uuid
from pathlib import Path

from flask import Flask, request, redirect, url_for, render_template, abort, Response
from loguru import logger

from utils import config as cfg_utils
from utils import groups as group_utils
from utils import notifications, season
from db import utils as db_utils
from db.exceptions import UserNotFoundError, MatchInviteNotFoundError
from models.user import User
from models.match_invite import MatchInvite
from constants import common

CONFIG = cfg_utils.load(str(Path(__file__).resolve().parent.parent / "resources" / "config.yml"))

app = Flask(__name__, template_folder=str(Path(__file__).resolve().parent / "templates"))

user_repo, ntf_repo, rating_repo, meet_repo, metadata_repo, invite_repo = db_utils.get_repos(CONFIG)


def is_admin(req):
    admin_token = CONFIG["web"].get("adminToken")
    if not admin_token:
        return True

    token = req.args.get("token") or req.form.get("token") or req.headers.get("X-Admin-Token")
    return token == admin_token


def get_enabled_groups():
    return [group for group in CONFIG["generated"]["groups"] if group["enabled"]]


def generate_matches():
    users = user_repo.list(spec={"pause_in_weeks": "0"})
    for meet_group in group_utils.get_unique_meet_groups(users):
        if group_utils.check_group_enabled(group=meet_group, groups=CONFIG["generated"]["groups"]):
            meet_repo.create(
                uids=[user.id for user in users if user.meet_group == meet_group],
                additional_uids=group_utils.get_group_additional_users(meet_group, CONFIG["generated"]["groups"])
            )


def send_match_emails():
    meets = meet_repo.list(spec={"season": season.get()})
    for meet in meets:
        try:
            user1 = user_repo.get_by_id(meet.uid1)
            user2 = user_repo.get_by_id(meet.uid2)
        except UserNotFoundError as ex:
            logger.error(f"Unable to load users for meet {meet.id}: {ex}")
            continue

        try:
            invite1 = invite_repo.get_by_meet_user(meet.id, user1.id)
        except MatchInviteNotFoundError:
            invite1 = invite_repo.add(MatchInvite(
                meet_id=meet.id,
                uid=user1.id,
                token=uuid.uuid4().hex
            ))

        try:
            invite2 = invite_repo.get_by_meet_user(meet.id, user2.id)
        except MatchInviteNotFoundError:
            invite2 = invite_repo.add(MatchInvite(
                meet_id=meet.id,
                uid=user2.id,
                token=uuid.uuid4().hex
            ))

        subject, body, html_body = notifications.build_match_email(CONFIG, user1, user2, invite1.token)
        notifications.send_email_notification(
            CONFIG,
            ntf_repo,
            user1,
            f"{common.NTF_TYPES.match_proposal}_{meet.id}",
            subject,
            body,
            html_body=html_body
        )

        subject, body, html_body = notifications.build_match_email(CONFIG, user2, user1, invite2.token)
        notifications.send_email_notification(
            CONFIG,
            ntf_repo,
            user2,
            f"{common.NTF_TYPES.match_proposal}_{meet.id}",
            subject,
            body,
            html_body=html_body
        )


@app.get("/")
def index():
    return render_template(
        "index.html",
        groups=get_enabled_groups()
    )


@app.post("/join")
def join():
    email = request.form.get("email", "").strip().lower()
    full_name = request.form.get("full_name", "").strip()
    unit = request.form.get("unit", "").strip()
    bio = request.form.get("bio", "").strip()
    meet_group = request.form.get("meet_group", "").strip()

    if not email or not full_name or not meet_group:
        return render_template(
            "index.html",
            groups=get_enabled_groups(),
            error="Name, email, and community group are required."
        )

    try:
        user = user_repo.get_by_email(email)
        user.full_name = full_name
        user.unit = unit
        user.bio = bio
        user.meet_group = meet_group
        user.pause_in_weeks = "0"
        user_repo.update(user)
    except UserNotFoundError:
        user_repo.add(User(
            id=uuid.uuid4().hex,
            username=full_name,
            email=email,
            full_name=full_name,
            unit=unit,
            bio=bio,
            meet_group=meet_group,
            pause_in_weeks="0"
        ))

    return render_template("join_success.html", email=email)


@app.get("/admin")
def admin():
    if not is_admin(request):
        abort(401)

    users = user_repo.list()
    meets = meet_repo.list()
    user_map = {user.id: user for user in users}
    invite_status = {invite.meet_id: [] for invite in invite_repo.list()}
    for invite in invite_repo.list():
        invite_status.setdefault(invite.meet_id, []).append(invite)

    return render_template(
        "admin.html",
        users=users,
        meets=meets,
        invite_status=invite_status,
        user_map=user_map
    )


@app.post("/admin/generate-matches")
def admin_generate_matches():
    if not is_admin(request):
        abort(401)

    generate_matches()
    return redirect(url_for("admin", token=request.form.get("token")))


@app.post("/admin/send-matches")
def admin_send_matches():
    if not is_admin(request):
        abort(401)

    send_match_emails()
    return redirect(url_for("admin", token=request.form.get("token")))


@app.get("/admin/export/users")
def export_users():
    if not is_admin(request):
        abort(401)

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["id", "name", "email", "unit", "group", "bio", "pause_in_weeks"])
    for user in user_repo.list():
        writer.writerow([user.id, user.full_name, user.email, user.unit, user.meet_group, user.bio, user.pause_in_weeks])

    return Response(
        output.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": "attachment;filename=tenants.csv"}
    )


@app.get("/admin/export/matches")
def export_matches():
    if not is_admin(request):
        abort(401)

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["season", "tenant_1", "tenant_1_email", "tenant_2", "tenant_2_email", "status_1", "status_2"])

    for meet in meet_repo.list():
        try:
            user1 = user_repo.get_by_id(meet.uid1)
            user2 = user_repo.get_by_id(meet.uid2)
        except UserNotFoundError:
            continue

        try:
            invite1 = invite_repo.get_by_meet_user(meet.id, user1.id)
            status1 = invite1.status
        except MatchInviteNotFoundError:
            status1 = "pending"

        try:
            invite2 = invite_repo.get_by_meet_user(meet.id, user2.id)
            status2 = invite2.status
        except MatchInviteNotFoundError:
            status2 = "pending"

        writer.writerow([
            meet.season,
            user1.full_name,
            user1.email,
            user2.full_name,
            user2.email,
            status1,
            status2
        ])

    return Response(
        output.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": "attachment;filename=matches.csv"}
    )


@app.get("/respond/<token>/<decision>")
def respond(token, decision):
    if decision not in ["accept", "decline"]:
        abort(400)

    try:
        invite = invite_repo.get_by_token(token)
    except MatchInviteNotFoundError:
        return render_template("response.html", message="Sorry, that response link is no longer valid.")

    invite.status = decision
    invite_repo.update(invite)

    message = "Thanks for responding! We will let your neighbor know."
    return render_template("response.html", message=message)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
