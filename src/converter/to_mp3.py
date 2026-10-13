"""Converts one queued video to MP3 and announces the result on the MP3 queue."""

import json
import os
import subprocess
import tempfile

MP3_QUEUE = os.environ.get("MP3_QUEUE", "mp3")


def extract_audio(video_path, mp3_path):
    """Strip the video stream and encode the audio as VBR MP3 with ffmpeg."""
    subprocess.run(
        ["ffmpeg", "-y", "-loglevel", "error", "-i", video_path,
         "-vn", "-codec:a", "libmp3lame", "-q:a", "2", mp3_path],
        check=True,
        capture_output=True,
    )


def process(body, fs_videos, fs_mp3s, channel, object_id=None):
    """Handle one message from the video queue.

    1. read the uploaded video from GridFS
    2. convert it to MP3 with ffmpeg
    3. store the MP3 in GridFS (tagged with the owner's username)
    4. publish {video_fid, mp3_fid, username} to the MP3 queue

    If publishing fails, the stored MP3 is deleted and the error is re-raised
    so the consumer can reject the message.
    """
    if object_id is None:
        from bson import ObjectId as object_id

    message = json.loads(body)
    video = fs_videos.get(object_id(message["video_fid"]))

    with tempfile.TemporaryDirectory() as workdir:
        video_path = os.path.join(workdir, "input")
        mp3_path = os.path.join(workdir, "output.mp3")
        with open(video_path, "wb") as f:
            f.write(video.read())

        extract_audio(video_path, mp3_path)

        with open(mp3_path, "rb") as f:
            mp3_fid = fs_mp3s.put(
                f.read(),
                filename=f"{message['video_fid']}.mp3",
                content_type="audio/mpeg",
                username=message["username"],
            )

    message["mp3_fid"] = str(mp3_fid)
    try:
        channel.queue_declare(queue=MP3_QUEUE, durable=True)
        channel.basic_publish(
            exchange="",
            routing_key=MP3_QUEUE,
            body=json.dumps(message),
            properties=_persistent(),
        )
    except Exception:
        fs_mp3s.delete(mp3_fid)
        raise

    return message


def _persistent():
    import pika

    return pika.BasicProperties(delivery_mode=pika.DeliveryMode.Persistent)
