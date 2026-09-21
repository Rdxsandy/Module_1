"""
services/vms_service.py

Resolves a Camera's real RTSP URL without ever storing VMS credentials in
the database or returning them from the API.

Problem this solves: pasting `rtsp://user:pass@host/...` into each of 30
cameras' stream_url means (a) re-entering the same credentials 30 times,
(b) storing them in plaintext in the cameras table, and (c) GET /api/cameras
returning stream_url to every logged-in user — including non-admins —
leaking the VMS password into their browser's network tab.

Instead: the VMS host/port/username/password live once in backend/.env,
and each Camera just stores which channel number (1..N) on that VMS it
corresponds to. The real URL is built here, on demand, only where it's
actually used to open a connection (never serialized back to the frontend).

A camera can still fall back to a fully manual stream_url (for a
standalone camera not behind the shared VMS) — vms_channel takes priority
when both are set.
"""
import os
from urllib.parse import quote

from app.models.camera import Camera

# Default assumes a Dahua/HikVision-style multi-channel NVR/VMS URL scheme
# (the most common one). Sentinel's actual RTSP path may differ — check its
# documentation or capture the URL your NVR viewer/ONVIF client uses, then
# set VMS_URL_TEMPLATE in backend/.env to match. Placeholders available:
# {username} {password} {host} {port} {channel}
DEFAULT_URL_TEMPLATE = "rtsp://{username}:{password}@{host}:{port}/cam/realmonitor?channel={channel}&subtype=0"


def get_vms_config() -> dict:
    """Non-secret VMS config for the frontend (channel picker range, and
    whether shared credentials are configured at all) — never includes the
    username/password."""
    host = os.getenv("VMS_HOST")
    return {
        "configured": bool(host),
        "channel_count": int(os.getenv("VMS_CHANNEL_COUNT", "30")),
    }


def resolve_stream_url(camera: Camera) -> str | None:
    """The URL to actually connect cv2.VideoCapture to for this camera —
    built from the shared VMS env config if vms_channel is set, otherwise
    the camera's own manual stream_url. Returns None if neither is usable."""
    if camera.vms_channel is not None:
        host = os.getenv("VMS_HOST")
        if not host:
            return None
        template = os.getenv("VMS_URL_TEMPLATE", DEFAULT_URL_TEMPLATE)
        # RTSP userinfo (rtsp://user:pass@host) breaks if either value
        # contains a reserved URL character — an email username's own "@"
        # is the classic case (must become %40). Percent-encode both here
        # so VMS_USERNAME/VMS_PASSWORD in .env can just hold the raw values.
        return template.format(
            username=quote(os.getenv("VMS_USERNAME", ""), safe=""),
            password=quote(os.getenv("VMS_PASSWORD", ""), safe=""),
            host=host,
            port=os.getenv("VMS_PORT", "554"),
            channel=camera.vms_channel,
        )
    return camera.stream_url or None
