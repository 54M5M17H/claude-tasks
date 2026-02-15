#!/bin/bash
EVENT="$1"
cat > /dev/null

# Validate event name against allowlist
case "$EVENT" in
  PermissionRequest|PostToolUseFailure|Stop|TaskCompleted|PreCompact|SessionEnd) ;;
  *) exit 0 ;;
esac

if [ -z "$AITASK_FILE" ] || [ ! -f "$AITASK_FILE" ]; then
  exit 0
fi

sed -i '' "s/^\*\*Status\*\*: .*/**Status**: $EVENT/" "$AITASK_FILE"
TIMESTAMP=$(date '+%A %-d %B %Y %H:%M:%S')
sed -i '' "s|^\*\*Last Updated Date/Time\*\*: .*|**Last Updated Date/Time**: $TIMESTAMP|" "$AITASK_FILE"
exit 0
