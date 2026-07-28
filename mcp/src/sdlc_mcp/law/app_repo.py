"""The coding toolbelt: read/write/search/git/run over the app repo's worktree.

Lets the connected Claude edit a project's code through the MCP — read files,
search, write changes on a feature branch, run the project's tests, commit — so
a task can go from request to a real branch (then a PR, see integrations).

Every path is confined to the repo root: ``..`` escapes and absolute paths are
rejected (symlinks are resolved, so a link out of the tree is caught too). Pure
filesystem/subprocess logic — the service layer adds audit/transcript records.
"""

from __future__ import annotations

import subprocess
from pathlib import Path


class AppRepoError(Exception):
    """A toolbelt operation was invalid (bad path, git failure, …)."""


def _safe(repo: Path, rel: str) -> Path:
    """Resolve ``rel`` inside ``repo``; reject anything that escapes it."""
    root = repo.resolve()
    target = (root / rel).resolve()
    if target != root and root not in target.parents:
        raise AppRepoError(f"path escapes the repo: {rel!r}")
    return target


# --------------------------------------------------------------------- files
def read_file(repo: Path, rel: str, *, max_bytes: int = 400_000) -> str:
    p = _safe(repo, rel)
    if not p.is_file():
        raise AppRepoError(f"not a file: {rel}")
    data = p.read_text(encoding="utf-8", errors="replace")
    if len(data) > max_bytes:
        return data[:max_bytes] + f"\n… [truncated at {max_bytes} chars]"
    return data


def write_file(repo: Path, rel: str, content: str) -> dict:
    p = _safe(repo, rel)
    if p.is_dir():
        raise AppRepoError(f"is a directory: {rel}")
    existed = p.exists()
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding="utf-8")
    return {"path": rel, "bytes": len(content.encode("utf-8")), "existed": existed}


def list_dir(repo: Path, rel: str = ".") -> list[dict]:
    p = _safe(repo, rel)
    if not p.is_dir():
        raise AppRepoError(f"not a directory: {rel}")
    out = []
    for c in sorted(p.iterdir(), key=lambda x: (x.is_file(), x.name)):
        if c.name == ".git":
            continue
        out.append({"name": c.name, "type": "dir" if c.is_dir() else "file"})
    return out


def search(repo: Path, pattern: str, *, max_results: int = 200) -> list[dict]:
    """Fixed-string search over tracked files via ``git grep``."""
    proc = _git(repo, ["grep", "-n", "-I", "-F", "-e", pattern])
    if proc.returncode not in (0, 1):  # 1 == no matches
        raise AppRepoError(f"git grep: {proc.stderr.strip()}")
    results = []
    for line in proc.stdout.splitlines()[:max_results]:
        parts = line.split(":", 2)
        if len(parts) == 3:
            results.append(
                {"file": parts[0], "line": int(parts[1]), "text": parts[2]}
            )
    return results


# ----------------------------------------------------------------------- git
def _git(repo: Path, args: list[str], *, timeout: int = 120) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", *args], cwd=repo, capture_output=True, text=True, timeout=timeout
    )


def current_branch(repo: Path) -> str:
    return _git(repo, ["rev-parse", "--abbrev-ref", "HEAD"]).stdout.strip()


def create_branch(repo: Path, name: str, base: str | None = None) -> dict:
    args = ["checkout", "-B", name] + ([base] if base else [])
    proc = _git(repo, args)
    if proc.returncode != 0:
        raise AppRepoError(f"git checkout: {proc.stderr.strip()}")
    return {"branch": name, "base": base}


def commit_all(
    repo: Path,
    message: str,
    *,
    author_name: str = "sdlc-mcp",
    author_email: str = "mcp@sdlc-platform",
) -> dict:
    _git(repo, ["add", "-A"])
    proc = _git(
        repo,
        [
            "-c", f"user.name={author_name}",
            "-c", f"user.email={author_email}",
            "commit", "-m", message,
        ],
    )
    if proc.returncode != 0:
        raise AppRepoError(
            "git commit: " + (proc.stdout.strip() or proc.stderr.strip())
        )
    sha = _git(repo, ["rev-parse", "--short", "HEAD"]).stdout.strip()
    return {"sha": sha, "message": message, "branch": current_branch(repo)}


def status(repo: Path) -> str:
    return _git(repo, ["status", "--short", "--branch"]).stdout


def diff(repo: Path, *, staged: bool = False) -> str:
    args = ["diff"] + (["--staged"] if staged else [])
    return _git(repo, args).stdout


# --------------------------------------------------------------------- checks
def run_check(repo: Path, cmd: str, *, timeout: int = 1800) -> dict:
    """Run a project command (e.g. the test cmd) in the repo; tail the output."""
    try:
        proc = subprocess.run(
            cmd, cwd=repo, shell=True, capture_output=True, text=True, timeout=timeout
        )
    except subprocess.TimeoutExpired:
        return {"code": None, "ok": False, "output_tail": f"timed out after {timeout}s"}
    out = ((proc.stdout or "") + (proc.stderr or "")).strip()
    return {"code": proc.returncode, "ok": proc.returncode == 0, "output_tail": out[-4000:]}
