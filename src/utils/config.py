# -*- coding: utf-8 -*-

import os
import time
import yaml

from datetime import date
from utils import groups


def load(yaml_path):
    with open(yaml_path, "r") as file:
        config = yaml.safe_load(file)

    slack_bot_token = os.environ.get("SLACK_BOT_TOKEN")
    slack_app_token = os.environ.get("SLACK_APP_TOKEN")

    email_smtp_host = os.environ.get("EMAIL_SMTP_HOST", config.get("email", {}).get("smtpHost", ""))
    email_smtp_port = os.environ.get("EMAIL_SMTP_PORT", config.get("email", {}).get("smtpPort", 587))
    email_smtp_user = os.environ.get("EMAIL_SMTP_USER", config.get("email", {}).get("smtpUser", ""))
    email_smtp_password = os.environ.get("EMAIL_SMTP_PASSWORD", config.get("email", {}).get("smtpPassword", ""))
    email_use_tls = os.environ.get("EMAIL_SMTP_USE_TLS", config.get("email", {}).get("useTLS", True))
    from_email = os.environ.get("EMAIL_FROM_EMAIL", config.get("communications", {}).get("fromEmail", ""))
    from_name = os.environ.get("EMAIL_FROM_NAME", config.get("communications", {}).get("fromName", ""))
    base_url = os.environ.get("APP_BASE_URL", config.get("web", {}).get("baseUrl", "http://localhost:5000"))

    db_password = os.environ.get("DATABASE_PASSWORD")

    config["slack"] = {
        "botToken": slack_bot_token,
        "appToken": slack_app_token
    }

    config["email"] = {
        "smtpHost": email_smtp_host,
        "smtpPort": email_smtp_port,
        "smtpUser": email_smtp_user,
        "smtpPassword": email_smtp_password,
        "useTLS": str(email_use_tls).lower() not in ["false", "0", "no"]
    }

    config["communications"] = {
        "defaultChannel": config.get("communications", {}).get("defaultChannel", "email"),
        "fromEmail": from_email,
        "fromName": from_name
    }

    config["web"] = {
        "baseUrl": base_url,
        "adminToken": os.environ.get("ADMIN_TOKEN", config.get("web", {}).get("adminToken", ""))
    }

    config["database"]["password"] = db_password

    config["generated"] = {}
    config["generated"]["groups"] = groups.get_groups(config["bot"]["locations"], config["bot"]["groups"])

    return config


def get_week_info(config):
    if config["devMode"]["enabled"]:
        weekday = int(config["devMode"]["weekday"])
        hour = int(config["devMode"]["hour"])
    else:
        weekday = date.today().weekday() + 1
        hour = int(time.strftime("%H"))

    return weekday, hour
