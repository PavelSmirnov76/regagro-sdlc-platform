"""Real Telegram delivery via the Bot API (stdlib urllib, no extra deps)."""

from __future__ import annotations

import io
import os
import urllib.request
import uuid

from .base import DeliveryResult


def _multipart(boundary: str, fields: dict[str, str], file_tuple) -> bytes:
    name, filename, data = file_tuple
    buf = io.BytesIO()
    for k, v in fields.items():
        buf.write(f"--{boundary}\r\n".encode())
        buf.write(f'Content-Disposition: form-data; name="{k}"\r\n\r\n'.encode())
        buf.write(f"{v}\r\n".encode())
    buf.write(f"--{boundary}\r\n".encode())
    buf.write(
        f'Content-Disposition: form-data; name="{name}"; filename="{filename}"\r\n'.encode()
    )
    buf.write(b"Content-Type: application/octet-stream\r\n\r\n")
    buf.write(data)
    buf.write(b"\r\n")
    buf.write(f"--{boundary}--\r\n".encode())
    return buf.getvalue()


class RealTelegramSender:
    def __init__(self, token: str, chat_id: str) -> None:
        self.token = token
        self.chat_id = chat_id

    def send_document(self, *, path, caption=None) -> DeliveryResult:
        if not (self.token and self.chat_id):
            return DeliveryResult(False, "no telegram credentials", used_fake=False)
        if not os.path.exists(path):
            return DeliveryResult(False, f"file not found: {path}", used_fake=False)

        boundary = uuid.uuid4().hex
        with open(path, "rb") as f:
            data = f.read()
        body = _multipart(
            boundary,
            {"chat_id": str(self.chat_id), "caption": caption or ""},
            ("document", os.path.basename(path), data),
        )
        req = urllib.request.Request(
            f"https://api.telegram.org/bot{self.token}/sendDocument",
            data=body,
            headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
        )
        try:
            with urllib.request.urlopen(req, timeout=120) as resp:
                ok = 200 <= resp.status < 300
                return DeliveryResult(ok, f"telegram status {resp.status}", used_fake=False)
        except Exception as e:  # noqa: BLE001 — network/HTTP errors surface as failure
            return DeliveryResult(False, f"telegram failed: {e}", used_fake=False)
