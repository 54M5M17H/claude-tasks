# claude-tasks

## What this is

A workflow for managing AI agent tasks using vimwiki. Create tasks as wiki files, launch Claude Code agents from vim with a single keypress, and track progress through a simple todo -> wip -> done lifecycle.

## Prerequisites

- [vim](https://www.vim.org/) or [neovim](https://neovim.io/)
- [vimwiki](https://github.com/vimwiki/vimwiki) plugin installed
- [tmux](https://github.com/tmux/tmux) -- tasks launch in new tmux windows, so vim must be running inside a tmux session
- [Claude Code](https://docs.anthropic.com/en/docs/claude-code) CLI installed and authenticated

## Vimwiki directory structure

The launcher script reads `g:vimwiki_list[0].path` from your vim config to find your wiki. Inside that directory, tasks are organised into three subdirectories representing their lifecycle stage:

```
~/vimwiki/              # (or wherever g:vimwiki_list[0].path points)
├── index.wiki          # Dashboard -- links to tasks across all stages
├── todo/               # New tasks waiting to be started
│   └── my-task.wiki
├── wip/                # Tasks currently being worked on by a Claude agent
│   └── active-task.wiki
└── done/               # Completed tasks
    └── finished-task.wiki
```

- `todo/` -- When you create a `.wiki` file here, the task template auto-loads. This is where you write task instructions before launching an agent.
- `wip/` -- When you press `<leader>ai`, the task file moves here automatically. Claude reads and updates the file in this directory as it works.
- `done/` -- Move completed tasks here with `<leader>mv` for archival.

See `examples/` for a sample dashboard and tasks in each stage.

## Setup

1. Clone the repo:
   ```bash
   git clone <repo-url> ~/repos/claude-tasks
   ```

2. Add to your vim config (`init.vim` or `.vimrc`):
   ```vim
   " Configure vimwiki with your wiki path
   let g:vimwiki_list = [{'path': '~/vimwiki'}]

   " Load the task launcher
   source ~/repos/claude-tasks/vimwiki_launcher.vim
   ```
   The launcher reads `g:vimwiki_list[0].path` to find your wiki, so this must be set before the `source` line.

3. Create the directory structure:
   ```bash
   mkdir -p ~/vimwiki/{todo,wip,done}
   ```

4. Generate Claude config and paste into `~/.claude/CLAUDE.md`:
   ```bash
   ./generate-claude-config.sh          # defaults to ~/vimwiki
   ./generate-claude-config.sh ~/wiki   # custom path
   ```

5. (Optional) Install Claude Code hooks for automatic status updates:
   ```bash
   ./install-hooks.sh
   ```
   This registers hooks that automatically update your task file's Status field when Claude events occur (permission requests, failures, session end, etc.). Requires `jq`.

## How it works

Tasks follow a three-stage lifecycle:

1. **Create** -- Write a new task file in `todo/`. When you create a `.wiki` file in the `todo/` directory, the task template auto-loads with fields for status, progress tracking, and metadata.

2. **Start** -- Press `<leader>ai` to launch the task. The file automatically moves from `todo/` to `wip/`, a new tmux window opens, and Claude Code starts reading the task file for instructions.

3. **Track** -- While working, Claude periodically updates the WIP file with its current status and progress. You can check on any task by opening its wiki file.

4. **Complete** -- When the work is done, move the task to `done/` with `<leader>mv`.

## Key bindings

| Binding | Command | Description |
|---|---|---|
| `<leader>ai` | `:AITask` | Launch Claude agent for current task |
| `<leader>t` | | Convert text to linked task |
| `<leader>mv` | `:VimwikiMv` | Move task between directories |

## Customization

- Modify `templates/task.wiki` to change the task template fields.
- The template supports any fields -- add or remove as needed for your workflow.
