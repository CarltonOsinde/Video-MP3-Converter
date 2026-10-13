"""Converter worker: consumes the video queue and converts each upload to MP3.

Run several replicas to convert in parallel. prefetch_count=1 means a worker
only takes a new job once it has acknowledged the previous one.
"""

import logging
import os
import sys

import gridfs
import pika
from pymongo import MongoClient

import to_mp3

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("converter")

VIDEO_QUEUE = os.environ.get("VIDEO_QUEUE", "video")


def main():
    client = MongoClient(os.environ["MONGO_URI"])
    fs_videos = gridfs.GridFS(client.videos)
    fs_mp3s = gridfs.GridFS(client.mp3s)

    connection = pika.BlockingConnection(pika.ConnectionParameters(host=os.environ["RABBITMQ_HOST"]))
    channel = connection.channel()
    channel.queue_declare(queue=VIDEO_QUEUE, durable=True)
    channel.basic_qos(prefetch_count=1)

    def on_message(ch, method, properties, body):
        try:
            result = to_mp3.process(body, fs_videos, fs_mp3s, ch)
            log.info("converted video %s -> mp3 %s", result["video_fid"], result["mp3_fid"])
            ch.basic_ack(delivery_tag=method.delivery_tag)
        except Exception:
            # Don't requeue: a video that fails once (e.g. corrupt file) would fail forever.
            log.exception("conversion failed; rejecting message")
            ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)

    channel.basic_consume(queue=VIDEO_QUEUE, on_message_callback=on_message)
    log.info("waiting for messages on '%s'", VIDEO_QUEUE)
    channel.start_consuming()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(0)
