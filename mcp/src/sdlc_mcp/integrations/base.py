"""Integration interfaces and their result types."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass
class PrResult:
    ok: bool
    url: str | None
    branch: str
    detail: str
    used_fake: bool


@dataclass
class ApkResult:
    ok: bool
    apk_path: str | None
    flavor: str
    detail: str
    used_fake: bool


@dataclass
class DeliveryResult:
    ok: bool
    detail: str
    used_fake: bool


class GitOps(Protocol):
    def open_pull_request(
        self, *, repo: str | None, base: str, head: str | None, title: str, body: str
    ) -> PrResult: ...


class ApkBuilder(Protocol):
    def build(
        self, *, repo: str | None, flavor: str, mode: str = "release"
    ) -> ApkResult: ...


class TelegramSender(Protocol):
    def send_document(self, *, path: str, caption: str | None = None) -> DeliveryResult: ...
