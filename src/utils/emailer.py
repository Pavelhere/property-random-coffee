# -*- coding: utf-8 -*-

import ssl
import smtplib
from email.message import EmailMessage
from loguru import logger


class EmailClient:
    def __init__(self, config, dry_run=True):
        email_config = config.get("email", {})
        smtp_config = email_config.get("smtp", {})

        self.host = smtp_config.get("host", "localhost")
        self.port = smtp_config.get("port", 25)
        self.username = smtp_config.get("username", "")
        self.password = smtp_config.get("password", "")
        self.use_tls = smtp_config.get("use_tls", True)

        self.from_address = email_config.get("fromAddress", "noreply@localhost")
        self.reply_to = email_config.get("replyTo", self.from_address)
        self.dry_run = dry_run

        self.resend_api_key = config.get("resend", {}).get("apiKey") or ""

    def send(self, *, to_address: str, subject: str, body: str, html: str | None = None, cc_address: str | None = None) -> None:
        if self.dry_run:
            logger.info("[DRY-RUN] Sending email to %s (cc: %s): %s", to_address, cc_address or "—", subject)
            logger.debug("Email body:\n%s", body)
            return

        if self.resend_api_key:
            self._send_resend(to_address=to_address, subject=subject, body=body, html=html, cc_address=cc_address)
        else:
            self._send_smtp(to_address=to_address, subject=subject, body=body, html=html, cc_address=cc_address)

    def _send_resend(self, *, to_address: str, subject: str, body: str, html: str | None, cc_address: str | None = None) -> None:
        import resend
        resend.api_key = self.resend_api_key
        params = {
            "from": self.from_address,
            "to": [to_address],
            "subject": subject,
            "text": body,
        }
        if cc_address:
            params["cc"] = [cc_address]
            params["reply_to"] = [to_address, cc_address]
        if html:
            params["html"] = html
        resend.Emails.send(params)
        logger.info("Sent email via Resend to %s (cc: %s): %s", to_address, cc_address or "—", subject)

    def _send_smtp(self, *, to_address: str, subject: str, body: str, html: str | None, cc_address: str | None = None) -> None:
        message = EmailMessage()
        message["Subject"] = subject
        message["From"] = self.from_address
        message["To"] = to_address
        message["Reply-To"] = self.reply_to
        if cc_address:
            message["Cc"] = cc_address
        message.set_content(body)
        if html:
            message.add_alternative(html, subtype="html")

        context = ssl.create_default_context()
        with smtplib.SMTP(self.host, self.port) as server:
            if self.use_tls:
                server.starttls(context=context)
            if self.username and self.password:
                server.login(self.username, self.password)
            server.send_message(message)
        logger.info("Sent email via SMTP to %s: %s", to_address, subject)
