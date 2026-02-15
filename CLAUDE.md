# claude-tasks

This repo defines a task management workflow for Claude Code agents using vimwiki.

## Repo structure

- `vimwiki_launcher.vim` — Vim functions that integrate vimwiki with Claude Code via tmux. Reads `g:vimwiki_list[0].path` at load time to find the user's wiki.
- `templates/task.wiki` — Template auto-loaded when creating new tasks in `todo/`. Defines the fields Claude uses for status reporting.
- `generate-claude-config.sh` — Generates a Status Reporting config block for `~/.claude/CLAUDE.md` with the user's wiki path and this repo's template path substituted in.
- `examples/` — Sample wiki files showing the todo/wip/done lifecycle.
- `hooks/task-status-hook.sh` — Claude Code hook that updates the task file's Status and Last Updated fields when session events fire. Reads `AITASK_FILE` env var set by the launcher.
- `install-hooks.sh` — Registers the task status hooks in `~/.claude/settings.json`. Idempotent.
- `README.md` — Setup guide and usage docs.

## Key design decisions

- The vim script resolves the wiki path from `g:vimwiki_list[0].path` — never hardcode `~/vimwiki` or any other path.
- Template path is resolved relative to the script's own location via `expand('<sfile>:p:h')` — never reference `~/.config/nvim/`.
- `generate-claude-config.sh` outputs absolute paths so Claude always knows where to write, regardless of working directory.
- This repo contains only the workflow tooling. User task data (their actual wiki files) lives separately and is never committed here.

## Editing rules

- **vimwiki_launcher.vim**: Test any changes by opening vim, creating a file in `todo/`, and running `:AITask`. Verify the template loads, the file moves to `wip/`, and a tmux window spawns.
- **templates/task.wiki**: Keep all existing fields. New fields can be added but don't remove any — Claude agents depend on the Status, Last Updated Date/Time, and Tmux Window fields.
- **generate-claude-config.sh**: Output must match the format Claude expects in CLAUDE.md. After changes, run the script and verify the output paths are correct.
- **README.md**: Keep setup steps numbered and in order. The `g:vimwiki_list` config must come before the `source` line in step 2.
- **examples/**: Keep examples realistic but generic. Don't include personal or company-specific content.
- **hooks/task-status-hook.sh**: Must always exit 0 to avoid blocking Claude. Must drain stdin. Only writes to the file if `AITASK_FILE` is set and exists.
- **install-hooks.sh**: Must be idempotent. Must resolve absolute paths dynamically (never hardcode paths).
