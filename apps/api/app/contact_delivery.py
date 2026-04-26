from __future__ import annotations

from email.message import EmailMessage
import os
import smtplib

from .config import env_bool
from .schemas import ContactRequest


def build_contact_email(payload: ContactRequest, recipient: str, sender: str) -> EmailMessage:
    message = EmailMessage()
    message["Subject"] = f"New Silico contact request from {payload.company}"
    message["From"] = sender
    message["To"] = recipient
    message["Reply-To"] = payload.email
    message.set_content(
        "\n".join(
            [
                "A new contact request was submitted on silico-labs.com.",
                "",
                f"Name: {payload.name}",
                f"Email: {payload.email}",
                f"Company: {payload.company}",
                "",
                "Message:",
                payload.message,
            ]
        )
    )
    return message


def send_contact_email(payload: ContactRequest, recipient: str) -> None:
    smtp_host = os.getenv("SMTP_HOST", "").strip()
    if not smtp_host:
        raise ValueError("SMTP_HOST is not configured.")

    smtp_port_raw = os.getenv("SMTP_PORT", "587").strip() or "587"
    try:
        smtp_port = int(smtp_port_raw)
    except ValueError as exc:
        raise ValueError("SMTP_PORT must be an integer.") from exc

    smtp_username = os.getenv("SMTP_USERNAME", "").strip()
    smtp_password = os.getenv("SMTP_PASSWORD", "")
    if smtp_username and not smtp_password:
        raise ValueError("SMTP_PASSWORD is required when SMTP_USERNAME is set.")

    sender = os.getenv("SMTP_FROM_EMAIL", "").strip() or smtp_username or recipient
    use_ssl = env_bool("SMTP_USE_SSL", False)
    use_starttls = env_bool("SMTP_USE_STARTTLS", not use_ssl)

    message = build_contact_email(payload, recipient, sender)

    try:
        if use_ssl:
            with smtplib.SMTP_SSL(smtp_host, smtp_port, timeout=10.0) as client:
                if smtp_username:
                    client.login(smtp_username, smtp_password)
                client.send_message(message)
            return

        with smtplib.SMTP(smtp_host, smtp_port, timeout=10.0) as client:
            client.ehlo()
            if use_starttls:
                client.starttls()
                client.ehlo()
            if smtp_username:
                client.login(smtp_username, smtp_password)
            client.send_message(message)
    except Exception as exc:  # pragma: no cover - wrapped for clean API contract
        raise RuntimeError("SMTP send failed.") from exc
