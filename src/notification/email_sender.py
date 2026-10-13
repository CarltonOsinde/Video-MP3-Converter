"""Emails the uploader when their MP3 is ready to download."""

import json
import os
import smtplib
from email.message import EmailMessage


def build_message(message, sender, download_base_url):
    mp3_fid = message["mp3_fid"]
    email = EmailMessage()
    email["Subject"] = "Your MP3 is ready"
    email["From"] = sender
    email["To"] = message["username"]
    email.set_content(
        "Your video has been converted to MP3.\n\n"
        f"File id: {mp3_fid}\n"
        f"Download: {download_base_url}/download?fid={mp3_fid}\n"
        "(send your login token in the Authorization header)\n"
    )
    return email


def notify(body):
    """Send the 'MP3 ready' email for one message from the MP3 queue."""
    message = json.loads(body)
    email = build_message(
        message,
        sender=os.environ["SMTP_SENDER"],
        download_base_url=os.environ.get("DOWNLOAD_BASE_URL", "http://mp3converter.com"),
    )

    with smtplib.SMTP(os.environ["SMTP_HOST"], int(os.environ.get("SMTP_PORT", 587)), timeout=10) as smtp:
        if os.environ.get("SMTP_STARTTLS", "true").lower() == "true":
            smtp.starttls()
        if os.environ.get("SMTP_USER"):
            smtp.login(os.environ["SMTP_USER"], os.environ["SMTP_PASSWORD"])
        smtp.send_message(email)
