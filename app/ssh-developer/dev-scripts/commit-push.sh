#!/bin/bash
cd /repo
MSG="${1:-Update $(date +%Y-%m-%d_%H:%M)}"
[ -z "$(git status --porcelain)" ] && { echo "Nothing to commit."; exit 0; }
git add -A && git commit -m "$MSG"
git push origin "$(git branch --show-current)" 2>/dev/null || echo "Commit saved locally (no remote)."
git log --oneline -1
