#!/bin/bash
set -euo pipefail

SUPERPOWERS_DIR="${HOME}/.claude/plugins/obra-superpowers"

# Install superpowers if not already present
if [ ! -d "$SUPERPOWERS_DIR" ]; then
  git clone --quiet --depth=1 https://github.com/obra/superpowers.git "$SUPERPOWERS_DIR" 2>/dev/null || {
    echo '{"error": "superpowers install failed - no network access"}' >&2
    exit 0
  }
fi

# Run the superpowers session-start hook
for hook in "$SUPERPOWERS_DIR/hooks/session-start" "$SUPERPOWERS_DIR/hooks/session-start.sh"; do
  if [ -f "$hook" ]; then
    chmod +x "$hook" 2>/dev/null || true
    exec bash "$hook"
  fi
done

exit 0
