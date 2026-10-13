"""Stores uploads in GridFS and hands them to the converter via RabbitMQ."""

import json
import os

VIDEO_QUEUE = os.environ.get("VIDEO_QUEUE", "video")


class UploadError(Exception):
    pass


def upload(file, fs_videos, channel, username):
    """Save the video, then publish a conversion job. Returns the video file id.

    If publishing fails the stored video is deleted, so we never keep a file
    that nothing will ever process.
    """
    try:
        video_fid = fs_videos.put(file, filename=file.filename, username=username)
    except Exception as exc:
        raise UploadError("could not store the video") from exc

    message = {"video_fid": str(video_fid), "mp3_fid": None, "username": username}
    try:
        import pika

        channel.queue_declare(queue=VIDEO_QUEUE, durable=True)
        channel.basic_publish(
            exchange="",
            routing_key=VIDEO_QUEUE,
            body=json.dumps(message),
            properties=pika.BasicProperties(delivery_mode=pika.DeliveryMode.Persistent),
        )
    except Exception as exc:
        fs_videos.delete(video_fid)
        raise UploadError("could not queue the video for conversion") from exc

    return str(video_fid)


def find_mp3(fs_mp3s, fid):
    """Return the GridFS file for fid, or None if the id is malformed or unknown."""
    from bson import ObjectId
    from bson.errors import InvalidId
    from gridfs.errors import NoFile

    try:
        return fs_mp3s.get(ObjectId(fid))
    except (InvalidId, NoFile):
        return None
