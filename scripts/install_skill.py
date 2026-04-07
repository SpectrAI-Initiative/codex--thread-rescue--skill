#!/usr/bin/env python3

from __future__ import annotations

import argparse
import os
import shutil
from pathlib import Path


SKILL_NAME = "codex--thread-rescue--skill"


def parse_args() -> argparse.Namespace:
    default_codex_home = Path(os.environ.get("CODEX_HOME", Path.home() / ".codex"))
    parser = argparse.ArgumentParser(
        description="Install this skill into the local Codex skills directory.",
    )
    parser.add_argument(
        "--codex-home",
        default=str(default_codex_home),
        help="Codex home directory. Defaults to $CODEX_HOME or ~/.codex.",
    )
    parser.add_argument(
        "--dest",
        help="Optional explicit install directory. Defaults to <codex-home>/skills/" + SKILL_NAME,
    )
    return parser.parse_args()


def ignore_copy(_src: str, names: list[str]) -> set[str]:
    ignored: set[str] = set()
    for name in names:
        if name in {".git", "__pycache__", ".DS_Store"}:
            ignored.add(name)
        elif name.endswith(".pyc"):
            ignored.add(name)
    return ignored


def main() -> int:
    args = parse_args()
    repo_root = Path(__file__).resolve().parents[1]
    codex_home = Path(args.codex_home).expanduser().resolve()
    dest = Path(args.dest).expanduser().resolve() if args.dest else (codex_home / "skills" / SKILL_NAME).resolve()

    if repo_root == dest:
        print(f"[OK] Skill is already installed at {dest}")
        return 0

    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(repo_root, dest, dirs_exist_ok=True, ignore=ignore_copy)

    print(f"[OK] Installed {SKILL_NAME} to {dest}")
    print("[INFO] Restart Codex Desktop if it is already running.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
