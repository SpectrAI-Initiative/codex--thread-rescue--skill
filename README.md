# codex-desktop-thread-repair

Reusable Codex skill for repairing missing local project threads in Codex Desktop.

It targets the failure mode where old threads still exist in `state_5.sqlite`, but the Desktop sidebar and `codex://threads/<id>` deeplinks do not surface them for a workspace. In practice this often comes from provider-filtered thread visibility, stale global state pins, or both.

## What it includes

- `SKILL.md`: trigger metadata and operational workflow for Codex
- `scripts/repair_codex_desktop_threads.py`: deterministic repair script

## What the script does

- Reads workspace threads from `$CODEX_HOME/state_5.sqlite`
- Compares database results against `codex app-server` `thread/list` visibility
- Detects hidden threads that exist in the DB but are filtered out of the default Desktop list
- Patches `$CODEX_HOME/.codex-global-state.json` so the workspace and thread metadata are visible to Desktop
- Optionally rewrites hidden `model_provider` rows to the currently visible provider after creating backups
- Optionally restarts Codex Desktop on macOS

## Install as a local skill

Clone or copy this repository to:

```text
~/.codex/skills/desktop-thread-repair
```

After that, Codex can trigger the skill when a user asks to restore missing local Desktop threads.

## Run manually

Dry run:

```bash
python3 scripts/repair_codex_desktop_threads.py --cwd /absolute/path/to/project
```

Apply repairs and relaunch Desktop:

```bash
python3 scripts/repair_codex_desktop_threads.py --cwd /absolute/path/to/project --apply --restart-desktop
```

JSON summary:

```bash
python3 scripts/repair_codex_desktop_threads.py --cwd /absolute/path/to/project --print-json
```

## Notes

- The script is read-only unless `--apply` is provided.
- Before modifying state, it creates timestamped backups of the affected global state and SQLite database files.
- The current implementation is intended for local Codex Desktop setups on macOS.
