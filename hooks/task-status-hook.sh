#!/bin/bash
EVENT="$1"
cat > /dev/null

if [ -z "$AITASK_FILE" ] || [ ! -f "$AITASK_FILE" ]; then
  exit 0
fi

# Map event to status. UserPromptSubmit clears terminal hook states
# (Stop, SessionEnd, etc.) back to Running so tasks don't stay stuck.
case "$EVENT" in
  UserPromptSubmit)
    grep -qE '^\*\*Status\*\*: (Stop|SessionEnd|PostToolUseFailure|PermissionRequest)$' "$AITASK_FILE" || exit 0
    STATUS="Running"
    ;;
  PermissionRequest|PostToolUseFailure|Stop|TaskCompleted|PreCompact|SessionEnd)
    STATUS="$EVENT"
    ;;
  *) exit 0 ;;
esac

sed -i '' "s/^\*\*Status\*\*: .*/**Status**: $STATUS/" "$AITASK_FILE"
TIMESTAMP=$(date '+%A %-d %B %Y %H:%M:%S')
sed -i '' "s|^\*\*Last Updated Date/Time\*\*: .*|**Last Updated Date/Time**: $TIMESTAMP|" "$AITASK_FILE"
exit 0
