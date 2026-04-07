---
name: desktop-thread-repair
description: Use when local Codex Desktop is missing old repo threads in the left sidebar, old project threads do not show up in the Desktop thread list, or codex://threads deeplinks do nothing. This skill diagnoses Codex Desktop thread visibility issues for a workspace, patches pinned thread metadata in global state, and, when needed, rewrites hidden thread model_provider values so Desktop stops filtering them out.
---

# Desktop Thread Repair

Use the bundled script for deterministic repair:

- Script: `scripts/repair_codex_desktop_threads.py`

## When to use

- Old local threads still exist on disk, but Desktop does not show them in the left sidebar
- `codex://threads/<id>` deeplinks are ineffective
- `thread/read` works by ID, but Desktop's default thread list is incomplete for a project

## Workflow

1. Run a dry run first:

```bash
python3 scripts/repair_codex_desktop_threads.py --cwd /absolute/path/to/project
```

2. If the script reports hidden threads, apply the repair and restart Desktop:

```bash
python3 scripts/repair_codex_desktop_threads.py --cwd /absolute/path/to/project --apply --restart-desktop
```

## What the script does

- Reads the project's threads from `$CODEX_HOME/state_5.sqlite`
- Queries `codex app-server` with default `thread/list` and provider-specific `thread/list`
- Detects threads that exist in the DB but are filtered out of Desktop's default list
- Patches `$CODEX_HOME/.codex-global-state.json` so the repo's threads are pinned and workspace-hinted
- If the hidden threads are only visible through a provider-specific query, rewrites those hidden rows to a visible provider after creating backups

## Important notes

- The script is dry-run by default. Writes require `--apply`.
- `--restart-desktop` is recommended after an apply run.
- If auto-detection of the visible provider is wrong for your setup, pass `--target-provider <provider>`.
