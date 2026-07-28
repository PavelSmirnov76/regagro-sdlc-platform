"""Pick real-or-fake integrations per capability, based on config/secrets."""

from __future__ import annotations

import shutil
from dataclasses import dataclass

from .apk_build import RealApkBuilder
from .base import ApkBuilder, GitOps, ReleaseUploader, TelegramSender
from .fakes import (
    FakeApkBuilder,
    FakeGitOps,
    FakeReleaseUploader,
    FakeTelegramSender,
)
from .git_ops import RealGitOps
from .github_release import RealReleaseUploader
from .telegram import RealTelegramSender


@dataclass
class Integrations:
    git: GitOps
    apk: ApkBuilder
    telegram: TelegramSender
    release: ReleaseUploader


def build(cfg) -> Integrations:
    use_gh = bool(cfg.app_repo and shutil.which("gh"))
    use_apk = bool(cfg.app_repo)
    use_tg = bool(cfg.telegram_bot_token and cfg.telegram_chat_id)
    return Integrations(
        git=RealGitOps() if use_gh else FakeGitOps(),
        apk=RealApkBuilder() if use_apk else FakeApkBuilder(),
        telegram=(
            RealTelegramSender(cfg.telegram_bot_token, cfg.telegram_chat_id)
            if use_tg
            else FakeTelegramSender()
        ),
        release=RealReleaseUploader() if use_gh else FakeReleaseUploader(),
    )
