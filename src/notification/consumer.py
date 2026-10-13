"""Notification worker: consumes the MP3 queue and emails the uploader."""

import logging
import os
import sys

import pika

import email_sender

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("notification")

MP3_QUEUE = os.environ.get("MP3_QUEUE", "mp3")


def main():
    connection = pika.BlockingConnection(pika.ConnectionParameters(host=os.environ["RABBITMQ_HOST"]))
    channel = connection.channel()
    channel.queue_declare(queue=MP3_QUEUE, durable=True)
    channel.basic_qos(prefetch_count=1)

    def on_message(ch, method, properties, body):
        try:
            email_sender.notify(body)
            log.info("notification sent")
            ch.basic_ack(delivery_tag=method.delivery_tag)
        except Exception:
            # Email failures are usually transient (SMTP outage), so requeue.
            log.exception("could not send notification; requeueing")
            ch.basic_nack(delivery_tag=method.delivery_tag, requeue=True)

    channel.basic_consume(queue=MP3_QUEUE, on_message_callback=on_message)
    log.info("waiting for messages on '%s'", MP3_QUEUE)
    channel.start_consuming()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(0)
