"""Real git/GitHub PR creation via the ``git`` and ``gh`` CLIs.

Only selected when an app repo is configured and ``gh`` is on PATH (and
authenticated — see ``docs/SETUP.md``). Never runs in tests.
"""

from __future__ import annotations

import subprocess

from .base import PrResult


def _run(args: list[str], cwd: str) -> subprocess.CompletedProcess:
    return subprocess.run(args, cwd=cwd, capture_output=True, text=True)


class RealGitOps:
    def open_pull_request(self, *, repo, base, head, title, body) -> PrResult:
        if not repo:
            return PrResult(False, None, head or "", "no app repo configured", used_fake=False)
        cur = _run(["git", "rev-parse", "--abbrev-ref", "HEAD"], repo)
        if cur.returncode != 0:
            return PrResult(False, None, head or "", f"git: {cur.stderr.strip()}", used_fake=False)
        branch = head or cur.stdout.strip()

        push = _run(["git", "push", "-u", "origin", branch], repo)
        if push.returncode != 0:
            return PrResult(False, None, branch, f"git push: {push.stderr.strip()}", used_fake=False)

        pr = _run(
            ["gh", "pr", "create", "--base", base, "--head", branch,
             "--title", title, "--body", body],
            repo,
        )
        if pr.returncode != 0:
            return PrResult(False, None, branch, f"gh pr create: {pr.stderr.strip()}", used_fake=False)
        url = pr.stdout.strip().splitlines()[-1] if pr.stdout.strip() else None
        return PrResult(True, url, branch, "PR created", used_fake=False)
