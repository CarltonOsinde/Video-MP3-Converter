import io
import json
import os
import sys
import types
import unittest
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

# pika is only needed against a real broker; provide a minimal stand-in if absent.
if "pika" not in sys.modules:
    try:
        import pika  # noqa: F401
    except ImportError:
        sys.modules["pika"] = types.SimpleNamespace(
            BasicProperties=lambda **kw: kw,
            DeliveryMode=types.SimpleNamespace(Persistent=2),
        )

import server  # noqa: E402
import storage  # noqa: E402


class FakeGridFS:
    def __init__(self, fail_put=False):
        self.files, self.deleted, self.fail_put = {}, [], fail_put

    def put(self, data, **meta):
        if self.fail_put:
            raise IOError("disk full")
        fid = f"fid{len(self.files) + 1}"
        self.files[fid] = (data, meta)
        return fid

    def delete(self, fid):
        self.deleted.append(fid)


class FakeChannel:
    def __init__(self, fail_publish=False):
        self.published, self.fail_publish = [], fail_publish

    def queue_declare(self, **kwargs):
        pass

    def basic_publish(self, **kwargs):
        if self.fail_publish:
            raise ConnectionError("broker down")
        self.published.append(kwargs)


class FakeMp3(io.BytesIO):
    def __init__(self, username):
        super().__init__(b"ID3fake-mp3-bytes")
        self.username = username


CLAIMS = {"username": "user@example.com", "admin": False}


class StorageTest(unittest.TestCase):
    def test_upload_stores_and_queues(self):
        fs, channel = FakeGridFS(), FakeChannel()
        file = types.SimpleNamespace(filename="clip.mp4")
        fid = storage.upload(file, fs, channel, "user@example.com")

        self.assertEqual(fid, "fid1")
        message = json.loads(channel.published[0]["body"])
        self.assertEqual(message, {"video_fid": "fid1", "mp3_fid": None, "username": "user@example.com"})

    def test_upload_deletes_video_when_publish_fails(self):
        fs, channel = FakeGridFS(), FakeChannel(fail_publish=True)
        with self.assertRaises(storage.UploadError):
            storage.upload(types.SimpleNamespace(filename="clip.mp4"), fs, channel, "u")
        self.assertEqual(fs.deleted, ["fid1"])

    def test_upload_reports_storage_failure(self):
        with self.assertRaises(storage.UploadError):
            storage.upload(types.SimpleNamespace(filename="clip.mp4"), FakeGridFS(fail_put=True), FakeChannel(), "u")


class GatewayRoutesTest(unittest.TestCase):
    def setUp(self):
        self.client = server.server.test_client()
        self.fs_videos, self.fs_mp3s, self.channel = FakeGridFS(), FakeGridFS(), FakeChannel()
        patches = [
            mock.patch.object(server, "get_gridfs", return_value=(self.fs_videos, self.fs_mp3s)),
            mock.patch.object(server, "get_channel", return_value=self.channel),
        ]
        for p in patches:
            p.start()
            self.addCleanup(p.stop)

    def test_upload_requires_valid_token(self):
        with mock.patch.object(server.auth_client, "validate", return_value=(None, ("invalid or expired token", 401))):
            response = self.client.post("/upload", headers={"Authorization": "Bearer bad"})
        self.assertEqual(response.status_code, 401)

    def test_upload_requires_exactly_one_file(self):
        with mock.patch.object(server.auth_client, "validate", return_value=(CLAIMS, None)):
            response = self.client.post("/upload", headers={"Authorization": "Bearer ok"}, data={})
        self.assertEqual(response.status_code, 400)

    def test_upload_queues_conversion(self):
        with mock.patch.object(server.auth_client, "validate", return_value=(CLAIMS, None)):
            response = self.client.post(
                "/upload",
                headers={"Authorization": "Bearer ok"},
                data={"file": (io.BytesIO(b"video-bytes"), "clip.mp4")},
                content_type="multipart/form-data",
            )
        self.assertEqual(response.status_code, 202)
        self.assertEqual(len(self.channel.published), 1)

    def test_download_returns_own_file(self):
        with mock.patch.object(server.auth_client, "validate", return_value=(CLAIMS, None)), \
             mock.patch.object(server.storage, "find_mp3", return_value=FakeMp3("user@example.com")):
            response = self.client.get("/download?fid=abc", headers={"Authorization": "Bearer ok"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.mimetype, "audio/mpeg")

    def test_download_forbids_other_users_file(self):
        with mock.patch.object(server.auth_client, "validate", return_value=(CLAIMS, None)), \
             mock.patch.object(server.storage, "find_mp3", return_value=FakeMp3("someone@else.com")):
            response = self.client.get("/download?fid=abc", headers={"Authorization": "Bearer ok"})
        self.assertEqual(response.status_code, 403)

    def test_download_unknown_file_is_404(self):
        with mock.patch.object(server.auth_client, "validate", return_value=(CLAIMS, None)), \
             mock.patch.object(server.storage, "find_mp3", return_value=None):
            response = self.client.get("/download?fid=abc", headers={"Authorization": "Bearer ok"})
        self.assertEqual(response.status_code, 404)


class AuthClientTest(unittest.TestCase):
    @mock.patch.dict(os.environ, {"AUTH_SVC_ADDRESS": "auth:5000"})
    def test_validate_returns_claims(self):
        fake = mock.Mock(status_code=200, json=lambda: CLAIMS)
        with mock.patch.object(server.auth_client.requests, "post", return_value=fake) as post:
            claims, error = server.auth_client.validate("Bearer token")
        self.assertIsNone(error)
        self.assertEqual(claims, CLAIMS)
        self.assertEqual(post.call_args.args[0], "http://auth:5000/validate")

    @mock.patch.dict(os.environ, {"AUTH_SVC_ADDRESS": "auth:5000"})
    def test_validate_handles_auth_outage(self):
        with mock.patch.object(server.auth_client.requests, "post", side_effect=server.auth_client.requests.ConnectionError):
            claims, error = server.auth_client.validate("Bearer token")
        self.assertIsNone(claims)
        self.assertEqual(error[1], 503)


if __name__ == "__main__":
    unittest.main()
