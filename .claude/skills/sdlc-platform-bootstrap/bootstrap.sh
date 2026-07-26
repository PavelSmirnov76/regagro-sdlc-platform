#!/usr/bin/env bash
#
# Bootstrap a new SDLC platform (the project-agnostic mcp/ engine + an sdlc/ tree)
# for another project, based on this platform as the template.
#
# Usage:
#   bootstrap.sh <target-dir> [existing-sdlc-source]
#
#   <target-dir>            where the new platform is created
#   [existing-sdlc-source]  optional: copy this existing sdlc/ tree; if omitted,
#                           a minimal 10-stage scaffold + PRD stub is created.
#
set -euo pipefail

TARGET="${1:?usage: bootstrap.sh <target-dir> [existing-sdlc-source]}"
SDLC_SRC="${2:-}"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PLATFORM_ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"
MCP_SRC="$PLATFORM_ROOT/mcp"

echo "Platform template: $PLATFORM_ROOT"
echo "New platform:      $TARGET"

mkdir -p "$TARGET"

# 1. Copy the project-agnostic mcp engine (without runtime state / secrets).
rsync -a \
  --exclude='.venv' --exclude='var' --exclude='.env' --exclude='uv.toml' \
  --exclude='__pycache__' --exclude='.pytest_cache' --exclude='*.egg-info' \
  "$MCP_SRC/" "$TARGET/mcp/"

# 2. The sdlc/ tree: copy an existing one, or scaffold a minimal valid tree.
if [ -n "$SDLC_SRC" ]; then
  echo "Copying sdlc/ from $SDLC_SRC"
  rsync -a --exclude='.obsidian' "$SDLC_SRC/" "$TARGET/sdlc/"
else
  echo "Scaffolding a minimal sdlc/ tree"
  for d in \
    0-vibes/prd/history 0-vibes/raw \
    1-business-tasks/planning \
    1-business-tasks/observation/errors 1-business-tasks/observation/warnings \
    1-business-tasks/observation/infos \
    2-specs/modules 2-specs/actors 2-specs/entities 2-specs/events 2-specs/use-cases \
    3-design/figma 4-tasks 5-results 6-eval 7-security-check 8-deploy 9-observation
  do
    mkdir -p "$TARGET/sdlc/$d"
  done
  cat > "$TARGET/sdlc/0-vibes/prd/PRD.md" <<'PRD'
# PRD — <project>

| | |
|---|---|
| Источник | новый проект |

## Purpose & scope

TBD.

## Goals and non-goals

TBD.

## Requirements

## Success metrics

TBD.
PRD
fi

# 3. Copy governing docs / gitignore / examples.
cp "$PLATFORM_ROOT/.gitignore" "$TARGET/.gitignore" 2>/dev/null || true
cp "$PLATFORM_ROOT/.mcp.json.example" "$TARGET/.mcp.json.example" 2>/dev/null || true
cp -R "$PLATFORM_ROOT/docs" "$TARGET/docs" 2>/dev/null || true

# 4. Init git.
if [ ! -d "$TARGET/.git" ]; then
  git -C "$TARGET" init -b main -q || true
fi

cat <<NEXT

Done. Next:
  cd "$TARGET/mcp"
  uv sync && uv run pytest && uv run python scripts/smoke.py

Then register the MCP server and set keys per docs/SETUP.md
(sections 3 and 4). If this machine has a root-owned ~/.local, add mcp/uv.toml
as described in docs/SETUP.md section 1.
NEXT
