#!/bin/bash
set -euo pipefail

# Resolve absolute path to the hooks directory
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
HOOK_SCRIPT="$SCRIPT_DIR/hooks/task-status-hook.sh"
SETTINGS_FILE="$HOME/.claude/settings.json"

# Validate prerequisites
if ! command -v jq &>/dev/null; then
  echo "Error: jq is required but not installed." >&2
  echo "Install it with: brew install jq (macOS) or apt-get install jq (Linux)" >&2
  exit 1
fi

if [ ! -f "$HOOK_SCRIPT" ]; then
  echo "Error: Hook script not found at $HOOK_SCRIPT" >&2
  exit 1
fi

if [ ! -f "$SETTINGS_FILE" ]; then
  echo "Error: Claude settings file not found at $SETTINGS_FILE" >&2
  echo "Run Claude Code at least once to generate it, or create it with: echo '{}' > $SETTINGS_FILE" >&2
  exit 1
fi

EVENTS=("UserPromptSubmit" "PermissionRequest" "PostToolUseFailure" "Stop" "TaskCompleted" "PreCompact" "SessionEnd")

# Read current settings
SETTINGS=$(cat "$SETTINGS_FILE")

for EVENT in "${EVENTS[@]}"; do
  COMMAND="$HOOK_SCRIPT $EVENT"

  # Remove any existing entry for this hook script path (idempotent)
  # Then add the new entry
  SETTINGS=$(echo "$SETTINGS" | jq --arg event "$EVENT" --arg cmd "$COMMAND" --arg hook_path "$HOOK_SCRIPT" '
    # Ensure .hooks object exists
    .hooks = (.hooks // {}) |
    # Ensure the event array exists
    .hooks[$event] = (.hooks[$event] // []) |
    # Remove any existing matcher that references our hook script
    .hooks[$event] = [
      .hooks[$event][] |
      select(
        (.hooks // []) | all(.command | tostring | contains($hook_path) | not)
      )
    ] |
    # Add our hook entry
    .hooks[$event] += [{"hooks": [{"type": "command", "command": $cmd}]}]
  ')
done

# Write back atomically
TMP=$(mktemp)
echo "$SETTINGS" | jq '.' > "$TMP" && mv "$TMP" "$SETTINGS_FILE"

echo "Installed task-status hooks in $SETTINGS_FILE"
echo ""
echo "Registered events:"
for EVENT in "${EVENTS[@]}"; do
  echo "  - $EVENT -> $HOOK_SCRIPT $EVENT"
done
echo ""
echo "Hook script: $HOOK_SCRIPT"
echo "Re-run this script at any time -- it is idempotent."
