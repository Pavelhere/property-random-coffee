# -*- coding: utf-8 -*-
"""Every email template must escape user-supplied content."""

from types import SimpleNamespace

from utils import emails

XSS = '<script>alert(1)</script>'
XSS_ESCAPED_MARKER = '&lt;script&gt;'


def _user(**overrides):
    base = dict(
        id="u1", username="Jane", full_name=f"Jane {XSS}", email="jane@example.com",
        bio=f'Baker "and" {XSS}', extra_info=f"Has kids, {XSS}", meet_group="coffee",
    )
    base.update(overrides)
    return SimpleNamespace(**base)


def test_confirmation_email_escapes_name():
    subject, body, html = emails.confirmation_email(f"Jane {XSS}", "Preston Ridge")
    assert XSS not in html
    assert XSS_ESCAPED_MARKER in html
    assert XSS in body  # plain text stays literal — no HTML context to break


def test_match_proposal_email_escapes_all_user_fields():
    subject, body, html = emails.match_proposal_email(
        recipient_name=f"Alex {XSS}",
        peer_name=f"Marcus {XSS}",
        peer_bio=f"Loves {XSS} ramen",
        peer_activity="coffee",
        peer_extra=f"New here, {XSS}",
        accept_url="http://testserver/respond?a=1&b=2",
        decline_url="http://testserver/respond?a=1&b=3",
        community_name="Preston Ridge",
    )
    assert XSS not in html
    assert html.count(XSS_ESCAPED_MARKER) >= 3  # recipient, peer name, bio, tag
    # URLs survive escaping in href context
    assert "http://testserver/respond?a=1&amp;b=2" in html
    assert "Coffee chat" in subject or "Preston Ridge" in subject


def test_match_proposal_email_without_bio_or_tags():
    subject, body, html = emails.match_proposal_email(
        recipient_name="Alex", peer_name="Marcus", peer_bio=None,
        peer_activity="walking", peer_extra=None,
        accept_url="http://x/a", decline_url="http://x/d",
        community_name="Preston Ridge",
    )
    assert "Marcus" in html and "neighborhood walk" in html.lower()
    assert '""' not in html  # no empty quoted bio block


def test_match_proposal_unknown_activity_falls_back():
    subject, body, html = emails.match_proposal_email(
        recipient_name="A", peer_name="B", peer_bio=None,
        peer_activity=None, peer_extra=None,
        accept_url="http://x/a", decline_url="http://x/d",
        community_name="C",
    )
    assert "meetup" in html


def test_connection_email_escapes_both_users_and_includes_contacts():
    u1, u2 = _user(), _user(id="u2", full_name=f"Sam {XSS}", email="sam@example.com")
    subject, plain, html = emails.connection_email(
        user1=u1, user2=u2, community_name="Preston Ridge",
    )
    assert XSS not in html
    assert XSS_ESCAPED_MARKER in html
    assert "jane@example.com" in html and "sam@example.com" in html
    assert "jane@example.com" in plain and "sam@example.com" in plain


def test_tags_capped_at_four():
    extra = ", ".join(f"tag{i}" for i in range(8))
    subject, body, html = emails.match_proposal_email(
        recipient_name="A", peer_name="B", peer_bio=None,
        peer_activity="coffee", peer_extra=extra,
        accept_url="http://x/a", decline_url="http://x/d",
        community_name="C",
    )
    assert "tag3" in html and "tag4" not in html
