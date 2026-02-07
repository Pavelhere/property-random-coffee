# -*- coding: utf-8 -*-

import smtplib
from email.message import EmailMessage

from loguru import logger


def send_email(config, to_email, subject, body, html_body=None):
    msg = EmailMessage()
    msg["Subject"] = subject
    from_email = config["communications"]["fromEmail"]
    if not from_email:
        logger.error("Email sender is not configured. Set communications.fromEmail or EMAIL_FROM_EMAIL.")
        return

    from_name = config["communications"].get("fromName")
    msg["From"] = f"{from_name} <{from_email}>" if from_name else from_email
    msg["To"] = to_email

    msg.set_content(body)
    if html_body:
        msg.add_alternative(html_body, subtype="html")

    if config["notifications"]["dryRun"]:
        logger.info("[DRY-RUN]: Email to {} with subject '{}'\n{}".format(to_email, subject, body))
        return

    smtp_host = config["email"]["smtpHost"]
    smtp_port = int(config["email"]["smtpPort"])
    smtp_user = config["email"]["smtpUser"]
    smtp_password = config["email"]["smtpPassword"]
    use_tls = config["email"]["useTLS"]

    try:
        with smtplib.SMTP(smtp_host, smtp_port) as server:
            server.ehlo()
            if use_tls:
                server.starttls()
                server.ehlo()
            if smtp_user and smtp_password:
                server.login(smtp_user, smtp_password)
            server.send_message(msg)
    except Exception as ex:
        logger.error(f"Failed to send email to {to_email}. Error: {ex}")
        raise
