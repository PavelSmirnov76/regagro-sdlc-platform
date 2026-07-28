"""Fakes — succeed and record the call. Used in tests and when keys are absent."""

from __future__ import annotations

from .base import ApkResult, DeliveryResult, PrResult


class FakeGitOps:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict]] = []

    def open_pull_request(self, *, repo, base, head, title, body) -> PrResult:
        self.calls.append(("open_pull_request", dict(repo=repo, base=base, head=head, title=title)))
        branch = head or "feature/pending"
        return PrResult(
            ok=True,
            url="https://example.invalid/pull/FAKE",
            branch=branch,
            detail="fake PR (no gh credentials / app repo configured)",
            used_fake=True,
        )


class FakeApkBuilder:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict]] = []

    def build(self, *, repo, flavor, mode="release") -> ApkResult:
        self.calls.append(("build", dict(repo=repo, flavor=flavor, mode=mode)))
        return ApkResult(
            ok=True,
            apk_path=f"/fake/build/app-{flavor}-{mode}.apk",
            flavor=flavor,
            detail="fake APK (no app repo / flutter configured)",
            used_fake=True,
        )


class FakeTelegramSender:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict]] = []

    def send_document(self, *, path, caption=None) -> DeliveryResult:
        self.calls.append(("send_document", dict(path=path, caption=caption)))
        return DeliveryResult(
            ok=True,
            detail="fake delivery (no telegram bot token / chat id)",
            used_fake=True,
        )
