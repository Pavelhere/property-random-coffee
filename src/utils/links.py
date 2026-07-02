# -*- coding: utf-8 -*-
"""Signed, expiring links for resident self-service (no accounts, no passwords).

Every emailed link that can change state carries an HMAC over
(purpose | uid | exp). Purposes are namespaced so a token for one flow can
never be replayed against another (a /preferences token is not an
/profile/edit token). Rotating RESPONSE_SECRET invalidates all links.
"""

import hashlib
import hmac
import time
from urllib.parse import urlencode

# Preferences links live in email footers for months — long TTL by design
# (an unsubscribe link that has expired is a spam complaint waiting to happen).
PREFS_TTL_SECONDS = 180 * 24 * 3600
# Profile-edit links are short-lived: they gate profile overwrites.
EDIT_TTL_SECONDS = 2 * 24 * 3600


def _sig(secret, purpose, uid, exp):
    data = f"{purpose}|{uid}|{exp}".encode("utf-8")
    return hmac.new(secret.encode("utf-8"), data, hashlib.sha256).hexdigest()


def signed_url(base_url, secret, path, purpose, uid, ttl):
    exp = int(time.time()) + ttl
    query = urlencode({
        "uid": uid,
        "exp": exp,
        "signature": _sig(secret, purpose, uid, exp),
    })
    return f"{base_url.rstrip('/')}{path}?{query}"


def verify(secret, purpose, uid, exp, signature, now=None):
    """True only for an untampered, unexpired token of this purpose."""
    if not all([uid, exp, signature]):
        return False
    try:
        exp_int = int(exp)
    except (TypeError, ValueError):
        return False
    if exp_int < (now if now is not None else time.time()):
        return False
    return hmac.compare_digest(_sig(secret, purpose, uid, exp_int), signature)


def preferences_url(base_url, secret, uid):
    return signed_url(base_url, secret, "/preferences", "prefs", uid, PREFS_TTL_SECONDS)


def edit_url(base_url, secret, uid):
    return signed_url(base_url, secret, "/profile/edit", "edit", uid, EDIT_TTL_SECONDS)
