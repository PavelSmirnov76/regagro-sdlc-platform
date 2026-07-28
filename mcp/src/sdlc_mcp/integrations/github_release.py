"""Deliver a build artifact as a GitHub Release asset via the ``gh`` CLI.

Selected when an app repo is configured and ``gh`` is on PATH (authenticated by
GH_TOKEN — see docs/SETUP.md). Server→GitHub works where other channels don't
(e.g. Telegram is unreachable from some networks), and a release asset has no
practical size limit. Never runs in tests.
"""

from __future__ import annotations

import subprocess

from .base import ReleaseResult


def _run(args: list[str], cwd: str, timeout: int = 1800) -> subprocess.CompletedProcess:
    return subprocess.run(args, cwd=cwd, capture_output=True, text=True, timeout=timeout)


class RealReleaseUploader:
    def upload(self, *, repo, tag, title, notes, file) -> ReleaseResult:
        if not repo:
            return ReleaseResult(False, None, "no app repo configured", used_fake=False)

        exists = _run(["gh", "release", "view", tag], repo, timeout=60).returncode == 0
        if exists:
            up = _run(["gh", "release", "upload", tag, file, "--clobber"], repo)
            if up.returncode != 0:
                return ReleaseResult(False, None, f"gh release upload: {up.stderr.strip()}", used_fake=False)
            view = _run(
                ["gh", "release", "view", tag, "--json", "url", "-q", ".url"], repo, timeout=60
            )
            url = view.stdout.strip() or None
        else:
            cre = _run(
                ["gh", "release", "create", tag, file, "--title", title, "--notes", notes],
                repo,
            )
            if cre.returncode != 0:
                return ReleaseResult(False, None, f"gh release create: {cre.stderr.strip()}", used_fake=False)
            url = cre.stdout.strip().splitlines()[-1] if cre.stdout.strip() else None

        return ReleaseResult(True, url, "released", used_fake=False)
