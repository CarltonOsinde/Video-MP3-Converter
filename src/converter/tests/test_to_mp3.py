"""Runs a real ffmpeg conversion on a generated one-second clip."""

import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import types
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

if "pika" not in sys.modules:
    try:
        import pika  # noqa: F401
    except ImportError:
        sys.modules["pika"] = types.SimpleNamespace(
            BasicProperties=lambda **kw: kw,
            DeliveryMode=types.SimpleNamespace(Persistent=2),
        )

import to_mp3  # noqa: E402


class FakeGridFS:
    def __init__(self):
        self.files, self.meta, self.deleted = {}, {}, []

    def put(self, data, **meta):
        fid = f"fid{len(self.files) + 1}"
        self.files[fid] = data if isinstance(data, bytes) else data.read()
        self.meta[fid] = meta
        return fid

    def get(self, fid):
        return io.BytesIO(self.files[fid])

    def delete(self, fid):
        self.deleted.append(fid)


class FakeChannel:
    def __init__(self, fail=False):
        self.published, self.fail = [], fail

    def queue_declare(self, **kwargs):
        pass

    def basic_publish(self, **kwargs):
        if self.fail:
            raise ConnectionError("broker down")
        self.published.append(kwargs)


@unittest.skipUnless(shutil.which("ffmpeg"), "ffmpeg not installed")
class ToMp3Test(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "clip.mp4")
            subprocess.run(
                ["ffmpeg", "-y", "-loglevel", "error",
                 "-f", "lavfi", "-i", "testsrc=duration=1:size=160x120:rate=10",
                 "-f", "lavfi", "-i", "sine=frequency=440:duration=1",
                 "-shortest", "-c:v", "mpeg4", "-c:a", "aac", path],
                check=True,
            )
            with open(path, "rb") as f:
                cls.video_bytes = f.read()

    def setUp(self):
        self.fs_videos, self.fs_mp3s = FakeGridFS(), FakeGridFS()
        self.video_fid = self.fs_videos.put(self.video_bytes)
        self.body = json.dumps({"video_fid": self.video_fid, "mp3_fid": None, "username": "user@example.com"})

    def test_converts_video_and_publishes_result(self):
        channel = FakeChannel()
        result = to_mp3.process(self.body, self.fs_videos, self.fs_mp3s, channel, object_id=str)

        mp3 = self.fs_mp3s.files[result["mp3_fid"]]
        self.assertTrue(mp3.startswith(b"ID3") or mp3[:2] == b"\xff\xfb", "output is not an MP3")
        self.assertEqual(self.fs_mp3s.meta[result["mp3_fid"]]["username"], "user@example.com")
        self.assertEqual(json.loads(channel.published[0]["body"])["mp3_fid"], result["mp3_fid"])

    def test_deletes_mp3_when_publish_fails(self):
        with self.assertRaises(ConnectionError):
            to_mp3.process(self.body, self.fs_videos, self.fs_mp3s, FakeChannel(fail=True), object_id=str)
        self.assertEqual(self.fs_mp3s.deleted, ["fid1"])

    def test_corrupt_video_raises(self):
        bad_fid = self.fs_videos.put(b"not a video")
        body = json.dumps({"video_fid": bad_fid, "mp3_fid": None, "username": "u"})
        with self.assertRaises(subprocess.CalledProcessError):
            to_mp3.process(body, self.fs_videos, self.fs_mp3s, FakeChannel(), object_id=str)


if __name__ == "__main__":
    unittest.main()
