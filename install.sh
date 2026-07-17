#!/bin/bash
# Autopsy installer — copies skills into ~/.claude/skills/ for Claude Code discovery.

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
SKILLS_DIR="$SCRIPT_DIR/skills"
TARGET_DIR="$HOME/.claude/skills"

INSTALLED=0
for skill_path in "$SKILLS_DIR"/*/SKILL.md; do
    [ -f "$skill_path" ] || continue
    name="$(basename "$(dirname "$skill_path")")"
    mkdir -p "$TARGET_DIR/$name"
    cp "$skill_path" "$TARGET_DIR/$name/SKILL.md"
    # Breadcrumb: the skill reads this instead of searching $HOME. Install is the
    # one moment the repo path is known for free; a find at run time costs seconds
    # (much worse on a Mac home full of Library/iCloud) on every single invocation.
    printf '%s\n' "$SCRIPT_DIR" > "$TARGET_DIR/$name/repo-path"
    echo "  Installed: $name -> $TARGET_DIR/$name/SKILL.md"
    INSTALLED=$((INSTALLED + 1))
done

if [ "$INSTALLED" -eq 0 ]; then
    echo "No skills found under $SKILLS_DIR/*/SKILL.md — nothing installed." >&2
    exit 1
fi

# Don't trust `command -v` alone: Windows ships a python3 stub that resolves on PATH
# and only advertises the Microsoft Store. Run the interpreter and see what answers.
PY=""
for candidate in python3 python; do
    if "$candidate" -c "import sys; sys.exit(0 if sys.version_info >= (3, 8) else 1)" >/dev/null 2>&1; then
        PY="$candidate"
        break
    fi
done

if [ -z "$PY" ]; then
    PY=python3
    echo "Warning: no working Python 3.8+ interpreter found on PATH." >&2
fi

echo ""
echo "Installed $INSTALLED skill(s) to $TARGET_DIR"
echo "Scripts are at: $SCRIPT_DIR/scripts/"
echo "You can now use /autopsy in Claude Code."
echo ""
echo "Quick test:"
echo "  $PY $SCRIPT_DIR/scripts/autopsy/run.py --days 7"
