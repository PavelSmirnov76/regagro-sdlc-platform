"""Real APK build via Flutter (fvm-aware). Only selected when an app repo is set."""

from __future__ import annotations

import os
import shutil
import subprocess

from .base import ApkResult


def _flutter_cmd(repo: str) -> list[str]:
    # This project pins Flutter with fvm; prefer it when available.
    uses_fvm = os.path.exists(os.path.join(repo, ".fvmrc")) or os.path.exists(
        os.path.join(repo, ".fvm")
    )
    if uses_fvm and shutil.which("fvm"):
        return ["fvm", "flutter"]
    return ["flutter"]


class RealApkBuilder:
    def build(self, *, repo, flavor, mode="release") -> ApkResult:
        if not repo:
            return ApkResult(False, None, flavor, "no app repo configured", used_fake=False)
        if mode not in ("release", "debug"):
            return ApkResult(False, None, flavor, f"bad mode: {mode}", used_fake=False)
        is_prod = "true" if flavor == "prod" else "false"
        # A debug build is signed with the auto-generated debug key, so it needs
        # no release keystore — the pragmatic choice for a shareable build.
        cmd = _flutter_cmd(repo) + ["build", "apk", f"--{mode}", "--flavor", flavor,
                                    f"--dart-define=IS_PROD={is_prod}"]
        try:
            proc = subprocess.run(
                cmd, cwd=repo, capture_output=True, text=True, timeout=1800
            )
        except Exception as e:  # noqa: BLE001 — surface any launch/timeout failure
            return ApkResult(False, None, flavor, f"build failed to run: {e}", used_fake=False)
        if proc.returncode != 0:
            tail = (proc.stderr or proc.stdout or "").strip()[-500:]
            return ApkResult(False, None, flavor, f"build failed: {tail}", used_fake=False)

        apk = os.path.join(
            repo, "build", "app", "outputs", "flutter-apk", f"app-{flavor}-{mode}.apk"
        )
        if os.path.exists(apk):
            return ApkResult(True, apk, flavor, f"built ({mode})", used_fake=False)
        return ApkResult(False, None, flavor, f"apk not found at {apk}", used_fake=False)
