import json
import os
import sys
import unittest
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import email_sender  # noqa: E402

MESSAGE = {"video_fid": "v1", "mp3_fid": "m1", "username": "user@example.com"}
ENV = {
    "SMTP_SENDER": "noreply@mp3converter.com",
    "SMTP_HOST": "smtp.example.com",
    "SMTP_PORT": "587",
    "SMTP_USER": "smtp-user",
    "SMTP_PASSWORD": "smtp-pass",
    "DOWNLOAD_BASE_URL": "http://mp3converter.com",
}


class EmailSenderTest(unittest.TestCase):
    def test_message_contains_download_link(self):
        email = email_sender.build_message(MESSAGE, "noreply@x.com", "http://host")
        self.assertEqual(email["To"], "user@example.com")
        self.assertIn("http://host/download?fid=m1", email.get_content())

    @mock.patch.dict(os.environ, ENV)
    def test_notify_sends_over_starttls_with_login(self):
        with mock.patch.object(email_sender.smtplib, "SMTP") as smtp_cls:
            email_sender.notify(json.dumps(MESSAGE))
        smtp = smtp_cls.return_value.__enter__.return_value
        smtp_cls.assert_called_once_with("smtp.example.com", 587, timeout=10)
        smtp.starttls.assert_called_once()
        smtp.login.assert_called_once_with("smtp-user", "smtp-pass")
        sent = smtp.send_message.call_args.args[0]
        self.assertEqual(sent["To"], "user@example.com")

    @mock.patch.dict(os.environ, {**ENV, "SMTP_STARTTLS": "false", "SMTP_USER": ""})
    def test_notify_supports_local_smtp_without_auth(self):
        with mock.patch.object(email_sender.smtplib, "SMTP") as smtp_cls:
            email_sender.notify(json.dumps(MESSAGE))
        smtp = smtp_cls.return_value.__enter__.return_value
        smtp.starttls.assert_not_called()
        smtp.login.assert_not_called()
        smtp.send_message.assert_called_once()


if __name__ == "__main__":
    unittest.main()
