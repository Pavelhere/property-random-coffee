# -*- coding: utf-8 -*-

from loguru import logger

from db.exceptions import NotificationNotFoundError
from models.notification import Notification
from utils import email as email_utils
from utils import season


def send_email_notification(config, ntf_repo, user, msg_type, subject, body, html_body=None):
    if not user.email:
        logger.warning(f"User {user.id} does not have an email address; cannot send {msg_type}")
        return

    try:
        ntf = ntf_repo.get({"uid": user.id, "type": msg_type, "season": season.get()})
    except NotificationNotFoundError:
        ntf = Notification(uid=user.id, season=season.get(), type=msg_type, status=False)
        ntf_repo.add(ntf)

    if ntf.status:
        logger.info(f"User {user.id} has already been notified about {msg_type}.")
        return

    email_utils.send_email(config, user.email, subject, body, html_body=html_body)
    ntf.status = True
    ntf_repo.update(ntf)
    logger.info(f"Email {msg_type} sent to {user.email}.")


def build_match_email(config, user, partner, invite_token):
    base_url = config["web"]["baseUrl"].rstrip("/")
    accept_url = f"{base_url}/respond/{invite_token}/accept"
    decline_url = f"{base_url}/respond/{invite_token}/decline"

    subject = "Your neighbor match for this week"
    body = (
        f"Hi {user.full_name or user.username},\n\n"
        "We found your weekly neighbor match! Here are the details:\n\n"
        f"Name: {partner.full_name or partner.username}\n"
        f"Unit: {partner.unit or 'Not listed'}\n"
        f"Email: {partner.email or 'Not listed'}\n"
        f"Interests: {partner.bio or 'Not listed'}\n\n"
        "Please let us know if you are up for connecting this week:\n"
        f"Accept: {accept_url}\n"
        f"Decline: {decline_url}\n\n"
        "Thanks for helping build community!"
    )

    html_body = (
        f"<p>Hi {user.full_name or user.username},</p>"
        "<p>We found your weekly neighbor match! Here are the details:</p>"
        "<ul>"
        f"<li><strong>Name:</strong> {partner.full_name or partner.username}</li>"
        f"<li><strong>Unit:</strong> {partner.unit or 'Not listed'}</li>"
        f"<li><strong>Email:</strong> {partner.email or 'Not listed'}</li>"
        f"<li><strong>Interests:</strong> {partner.bio or 'Not listed'}</li>"
        "</ul>"
        "<p>Please let us know if you are up for connecting this week:</p>"
        f"<p><a href=\"{accept_url}\">Accept</a> | "
        f"<a href=\"{decline_url}\">Decline</a></p>"
        "<p>Thanks for helping build community!</p>"
    )

    return subject, body, html_body


def build_no_match_email(user):
    subject = "We are still looking for your match"
    body = (
        f"Hi {user.full_name or user.username},\n\n"
        "We are still working on your neighbor match this week. "
        "If we find a match, you will receive another email.\n\n"
        "Thanks for your patience!"
    )
    return subject, body
