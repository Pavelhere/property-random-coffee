# -*- coding: utf-8 -*-

import os
import time
import yaml

from datetime import date


def _env_override(env_name, default=None):
    value = os.environ.get(env_name)
    if value is not None:
        return value
    return default


def load(yaml_path):
    with open(yaml_path, "r") as file:
        config = yaml.safe_load(file)

    config.setdefault("database", {})
    config.setdefault("email", {})
    config.setdefault("app", {})
    config.setdefault("community", {})

    config["database"]["password"] = _env_override("DATABASE_PASSWORD", config["database"].get("password"))

    config["app"]["baseUrl"] = _env_override("APP_BASE_URL", config["app"].get("baseUrl", "http://localhost:5000"))
    config["app"]["adminToken"] = _env_override("ADMIN_TOKEN", config["app"].get("adminToken", ""))
    config["app"]["responseSecret"] = _env_override("RESPONSE_SECRET", config["app"].get("responseSecret", ""))
    config["app"]["responseSecret"] = _env_override("RESPONSE_SECRET", config["app"].get("responseSecret", ""))

    email_config = config["email"]
    email_config.setdefault("smtp", {})
    smtp = email_config["smtp"]
    smtp["host"] = _env_override("SMTP_HOST", smtp.get("host", "localhost"))
    smtp["port"] = int(_env_override("SMTP_PORT", smtp.get("port", 25)))
    smtp["username"] = _env_override("SMTP_USERNAME", smtp.get("username", ""))
    smtp["password"] = _env_override("SMTP_PASSWORD", smtp.get("password", ""))
    smtp["use_tls"] = smtp.get("use_tls", True)

    email_config["fromAddress"] = _env_override("EMAIL_FROM", email_config.get("fromAddress", "noreply@localhost"))
    email_config["replyTo"] = _env_override("EMAIL_REPLY_TO", email_config.get("replyTo", email_config.get("fromAddress")))

    community_groups = []
    for name, definition in config["community"].get("groups", {}).items():
        community_groups.append({
            "name": name,
            "displayName": definition.get("displayName", name),
            "enabled": definition.get("enabled", True)
        })
    config["community"]["enabledGroups"] = [group for group in community_groups if group["enabled"]]
    config["community"]["allGroups"] = community_groups

    config.setdefault("generated", {})
    config["generated"]["groups"] = community_groups

    config.setdefault("notifications", {})
    config.setdefault("devMode", {"enabled": False, "weekday": 1, "hour": 0})
    config.setdefault("daemons", {"week": {"poolPeriod": 3600}})
    config.setdefault("log", {"rotation": "1 week"})

    return config


def get_week_info(config):
    if config["devMode"]["enabled"]:
        weekday = int(config["devMode"]["weekday"])
        hour = int(config["devMode"]["hour"])
    else:
        weekday = date.today().weekday() + 1
        hour = int(time.strftime("%H"))

    return weekday, hour
