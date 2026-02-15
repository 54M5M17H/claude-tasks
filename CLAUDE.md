# claude-tasks

This repo defines a task management workflow for Claude Code agents using vimwiki.

## Repo structure

- `vimwiki_launcher.vim` — Vim functions that integrate vimwiki with Claude Code via tmux. Reads `g:vimwiki_list[0].path` at load time to find the user's wiki.
- `claude_manager.py` — Terminal dashboard that monitors `wip/` tasks. Detects blocked, stale, crashed, and completed agents. Also detects hook-written statuses (`Stop`, `PermissionRequest`, `PostToolUseFailure`, `SessionEnd`) as needing attention. Runs in its own tmux window via `:AIManager`.
- `templates/task.wiki` — Template auto-loaded when creating new tasks in `todo/`. Defines the fields Claude uses for status reporting.
- `generate-claude-config.sh` — Generates a Status Reporting config block for `~/.claude/CLAUDE.md` with the user's wiki path and this repo's template path substituted in.
- `examples/` — Sample wiki files showing the todo/wip/done lifecycle.
- `hooks/task-status-hook.sh` — Claude Code hook that updates the task file's Status and Last Updated fields when session events fire. Reads `AITASK_FILE` env var set by the launcher. On `UserPromptSubmit`, resets terminal hook states (Stop, SessionEnd, etc.) to `Running` — preserves agent-set statuses like `Implementing`.
- `install-hooks.sh` — Registers the task status hooks in `~/.claude/settings.json`. Idempotent.
- `README.md` — Setup guide and usage docs.

## Key design decisions

- The vim script resolves the wiki path from `g:vimwiki_list[0].path` — never hardcode `~/vimwiki` or any other path.
- Template path is resolved relative to the script's own location via `expand('<sfile>:p:h')` — never reference `~/.config/nvim/`.
- `generate-claude-config.sh` outputs absolute paths so Claude always knows where to write, regardless of working directory.
- This repo contains only the workflow tooling. User task data (their actual wiki files) lives separately and is never committed here.
- Hook statuses and manager detection must stay in sync. The manager's `HOOK_ATTENTION_STATUSES` tuple must match the terminal states the hook writes. If adding a new hook event, update both `task-status-hook.sh` and `claude_manager.py`.
- Timestamps must be parseable by the manager. The hook writes `date '+%A %-d %B %Y %H:%M:%S'` (with year). The manager's `parse_timestamp` handles both with-year and without-year formats.
- tmux commands in the manager must use `:{window}` syntax (colon prefix) to target the current session, not `session:window` which can hit the wrong session when multiple sessions exist.

## Editing rules

- **claude_manager.py**: Stdlib only — no external dependencies. Test by creating a .wiki file in `wip/` with known attributes and running `python3 claude_manager.py`. Verify the dashboard renders, stale/blocked detection works, and `q` exits cleanly. The script reads task state from wiki files and cross-references `ps aux` + `tmux list-windows` for process detection. Three detection constants must be kept up to date: `COMPLETION_WORDS`, `BLOCKED_WORDS`, `HOOK_ATTENTION_STATUSES`.
- **vimwiki_launcher.vim**: Test any changes by opening vim, creating a file in `todo/`, and running `:AITask`. Verify the template loads, the file moves to `wip/`, and a tmux window spawns. For `:AIManager`, verify it opens `claude_manager.py` in a new tmux window.
- **templates/task.wiki**: Keep all existing fields. New fields can be added but don't remove any — Claude agents depend on the Status, Last Updated Date/Time, and Tmux Window fields.
- **generate-claude-config.sh**: Output must match the format Claude expects in CLAUDE.md. After changes, run the script and verify the output paths are correct.
- **README.md**: Keep setup steps numbered and in order. The `g:vimwiki_list` config must come before the `source` line in step 2.
- **examples/**: Keep examples realistic but generic. Don't include personal or company-specific content.
- **hooks/task-status-hook.sh**: Must always exit 0 to avoid blocking Claude. Must drain stdin. Only writes to the file if `AITASK_FILE` is set and exists. `UserPromptSubmit` is conditional — only overwrites terminal hook states, not agent-set statuses.
- **install-hooks.sh**: Must be idempotent. Must resolve absolute paths dynamically (never hardcode paths). Events array must include all events the hook script handles.
