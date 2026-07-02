# -*- coding: utf-8 -*-

import os
import yaml

from datetime import datetime
from zoneinfo import ZoneInfo

DEFAULT_TIMEZONE = "America/Chicago"


def _env_override(env_name, default=None):
    value = os.environ.get(env_name)
    if value is not None:
        return value
    return default


def _env_bool(env_name, default):
    value = os.environ.get(env_name)
    if value is None:
        return default
    return value.strip().lower() in ("1", "true", "yes", "on")


def load(yaml_path):
    with open(yaml_path, "r") as file:
        config = yaml.safe_load(file)

    config.setdefault("database", {})
    config.setdefault("email", {})
    config.setdefault("app", {})
    config.setdefault("community", {})

    # Railway-style MySQL env vars take precedence
    config["database"]["host"] = _env_override("MYSQLHOST", _env_override("DATABASE_HOST", config["database"].get("host", "127.0.0.1")))
    config["database"]["port"] = int(_env_override("MYSQLPORT", _env_override("DATABASE_PORT", config["database"].get("port", 3308))))
    config["database"]["db"] = _env_override("MYSQLDATABASE", _env_override("DATABASE_NAME", config["database"].get("db", "coffee")))
    config["database"]["username"] = _env_override("MYSQLUSER", _env_override("DATABASE_USER", config["database"].get("username", "root")))
    config["database"]["password"] = _env_override("MYSQLPASSWORD", _env_override("DATABASE_PASSWORD", config["database"].get("password")))

    config["app"]["baseUrl"] = _env_override("APP_BASE_URL", config["app"].get("baseUrl", "http://localhost:5000"))
    config["app"]["adminToken"] = _env_override("ADMIN_TOKEN", config["app"].get("adminToken", ""))
    config["app"]["responseSecret"] = _env_override("RESPONSE_SECRET", config["app"].get("responseSecret", ""))

    config["community"]["timezone"] = _env_override(
        "COMMUNITY_TIMEZONE", config["community"].get("timezone", DEFAULT_TIMEZONE)
    )

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

    config.setdefault("resend", {})
    config["resend"]["apiKey"] = _env_override("RESEND_API_KEY", config["resend"].get("apiKey", ""))

    community_groups = []
    for name, definition in config["community"].get("groups", {}).items():
        community_groups.append({
            "name": name,
            "displayName": definition.get("displayName", name),
            "enabled": definition.get("enabled", True)
        })
    config["community"]["enabledGroups"] = [group for group in community_groups if group["enabled"]]
    config["community"]["allGroups"] = community_groups

    config.setdefault("notifications", {})
    # Safe default: dry-run unless explicitly disabled (file or env).
    config["notifications"]["dryRun"] = _env_bool(
        "NOTIFICATIONS_DRY_RUN", config["notifications"].get("dryRun", True)
    )
    config.setdefault("devMode", {"enabled": False, "weekday": 1, "hour": 0})
    config.setdefault("log", {"rotation": "1 week"})

    return config


def community_now(config):
    """Current datetime in the property's timezone (never server-local)."""
    tz = ZoneInfo(config["community"].get("timezone", DEFAULT_TIMEZONE))
    return datetime.now(tz)


def get_week_info(config):
    if config["devMode"]["enabled"]:
        weekday = int(config["devMode"]["weekday"])
        hour = int(config["devMode"]["hour"])
    else:
        now = community_now(config)
        weekday = now.weekday() + 1
        hour = now.hour

    return weekday, hour
