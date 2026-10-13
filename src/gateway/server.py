"""API gateway: the only service exposed outside the cluster.

Endpoints
    POST /login              Basic auth, proxied to the auth service -> JWT
    POST /upload             Bearer JWT + multipart file             -> 202, queues conversion
    GET  /download?fid=<id>  Bearer JWT                              -> MP3 file
    GET  /health
"""

import os
from functools import lru_cache

from flask import Flask, jsonify, request, send_file

import auth_client
import storage

server = Flask(__name__)
server.config["MAX_CONTENT_LENGTH"] = int(os.environ.get("MAX_UPLOAD_MB", 200)) * 1024 * 1024


@lru_cache(maxsize=1)
def get_gridfs():
    """GridFS buckets for uploaded videos and converted MP3s (created on first use)."""
    import gridfs
    from pymongo import MongoClient

    client = MongoClient(os.environ["MONGO_URI"])
    return gridfs.GridFS(client.videos), gridfs.GridFS(client.mp3s)


def get_channel():
    """A RabbitMQ channel. Reconnects if the cached connection has dropped."""
    import pika

    connection = getattr(get_channel, "_connection", None)
    if connection is None or connection.is_closed:
        connection = pika.BlockingConnection(pika.ConnectionParameters(host=os.environ["RABBITMQ_HOST"]))
        get_channel._connection = connection
    return connection.channel()


@server.post("/login")
def login():
    token, error = auth_client.login(request.authorization)
    if error:
        return jsonify(message=error[0]), error[1]
    return token, 200


@server.post("/upload")
def upload():
    claims, error = auth_client.validate(request.headers.get("Authorization"))
    if error:
        return jsonify(message=error[0]), error[1]

    if len(request.files) != 1:
        return jsonify(message="exactly one file is required"), 400

    file = next(iter(request.files.values()))
    fs_videos, _ = get_gridfs()
    try:
        video_fid = storage.upload(file, fs_videos, get_channel(), claims["username"])
    except storage.UploadError as exc:
        return jsonify(message=str(exc)), 500

    return jsonify(message="upload accepted, conversion queued", video_fid=video_fid), 202


@server.get("/download")
def download():
    claims, error = auth_client.validate(request.headers.get("Authorization"))
    if error:
        return jsonify(message=error[0]), error[1]

    fid = request.args.get("fid")
    if not fid:
        return jsonify(message="fid is required"), 400

    _, fs_mp3s = get_gridfs()
    mp3 = storage.find_mp3(fs_mp3s, fid)
    if mp3 is None:
        return jsonify(message="file not found"), 404

    # Users may only download their own files; admins may download any.
    if getattr(mp3, "username", None) != claims["username"] and not claims.get("admin"):
        return jsonify(message="not allowed to access this file"), 403

    return send_file(mp3, mimetype="audio/mpeg", as_attachment=True, download_name=f"{fid}.mp3")


@server.get("/health")
def health():
    return jsonify(status="ok"), 200


if __name__ == "__main__":
    server.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))
