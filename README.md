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

```
                       ┌──────────────────────────────────────────┐
                       │              ~/vimwiki/                   │
                       │                                          │
                       │  todo/          wip/              done/  │
                       │  ┌──────┐     ┌──────┐          ┌─────┐ │
                       │  │ task │     │ task │          │task │ │
                       │  │ .wiki│     │ .wiki│          │.wiki│ │
                       │  └──┬───┘     └▲──▲──┘          └─────┘ │
                       │     │          │  │  ▲                   │
                       └─────┼──────────┼──┼──┼───────────────────┘
                             │          │  │  │
       ┌─────────────────────┘          │  │  │
       │  <leader>ai                    │  │  │
       │  moves todo/ -> wip/           │  │  │  reads wip/*.wiki
       │  opens tmux window             │  │  │  detects stale
       ▼                                │  │  │  timestamps
┌─────────────┐    reads task file      │  │  │
│   Vim +     ├─────────────────────────┘  │  │
│   Launcher  │                            │  │
│             │    sets AITASK_FILE env     │  │
└─────────────┘              │             │  │
                             │             │  │
                             ▼             │  │
                    ┌────────────────┐     │  │
                    │  Claude Code   │     │  │
                    │  (tmux window) │     │  │
                    │                │     │  │
                    │  reads task    │     │  │
                    │  instructions  ├─────┤  │  writes status,
                    │                │     │  │  progress, PR links
                    └───────┬────────┘     │  │
                            │              │  │
                 session events fire       │  │
                            │              │  │
                            ▼              │  │
                    ┌────────────────┐     │  │
                    │  Hooks         │     │  │
                    │                │     │  │
                    │ PermissionReq  ├─────┘  │  updates Status
                    │ ToolFailure    │        │  + timestamp
                    │ Stop           │        │
                    │ TaskCompleted  │        │
                    │ PreCompact     │        │
                    │ SessionEnd     │        │
                    └────────────────┘        │
                                              │
                    ┌────────────────┐        │
                    │  Manager       ├────────┘
                    │  (optional)    │  monitors wip/,
                    │                │  alerts on crashed agents
                    └────────────────┘
```

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
| | `:AIManager` | Open the task manager dashboard |

## Task Manager

`claude_manager.py` is a terminal dashboard that monitors all active tasks in `wip/`. It runs continuously in its own tmux window and alerts you when tasks need attention.

### What it monitors

- **Blocked/waiting tasks** -- Status contains words like "waiting", "blocked", "paused"
- **Crashed agents** -- No Claude process found for a task that isn't complete
- **Stale tasks** -- No wiki file update in the last 10 minutes (configurable)
- **Completed tasks** -- Status suggests the task is done and should be moved to `done/`

### Running the manager

From vim (opens in a new tmux window):
```
:AIManager
```

Or directly from the terminal:
```bash
python3 ~/repos/claude-tasks/claude_manager.py
```

### Options

```
python3 claude_manager.py [--wiki-path PATH] [--interval SECONDS] [--stale-minutes MINUTES] [--no-notifications]
```

| Flag | Default | Description |
|---|---|---|
| `--wiki-path` | `~/vimwiki` | Path to vimwiki root |
| `--interval` | `30` | Seconds between refreshes |
| `--stale-minutes` | `10` | Minutes before a task is flagged as stale |
| `--no-notifications` | off | Disable macOS desktop notifications |

### Dashboard controls

| Key | Action |
|---|---|
| `1`-`9` | Switch to that task's tmux window |
| `r` | Force immediate refresh |
| `q` | Quit the manager |

Desktop notifications (via macOS Notification Center) fire automatically for tasks that need attention or have stopped running. They deduplicate so you only get alerted once per issue.

### Prerequisites

- Python 3.9+ (ships with macOS)
- No external dependencies -- stdlib only

## Customization

- Modify `templates/task.wiki` to change the task template fields.
- The template supports any fields -- add or remove as needed for your workflow.
