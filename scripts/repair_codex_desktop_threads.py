#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import os
import select
import shutil
import sqlite3
import subprocess
import sys
import time
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class ThreadRecord:
    thread_id: str
    title: str
    cwd: str
    source: str
    model_provider: str
    updated_at: int


def parse_args() -> argparse.Namespace:
    home = Path(os.environ.get("CODEX_HOME", Path.home() / ".codex"))
    parser = argparse.ArgumentParser(
        description=(
            "Repair missing local Codex Desktop threads for a workspace by reconciling "
            "state_5.sqlite, Desktop global state, and app-server thread/list visibility."
        )
    )
    parser.add_argument("--cwd", required=True, help="Workspace root whose threads should appear in Desktop.")
    parser.add_argument("--codex-home", default=str(home), help="Codex home directory. Defaults to $CODEX_HOME or ~/.codex.")
    parser.add_argument("--apply", action="store_true", help="Apply repairs. Without this flag the script is read-only.")
    parser.add_argument("--restart-desktop", action="store_true", help="Quit and relaunch Codex Desktop after applying changes.")
    parser.add_argument(
        "--target-provider",
        default="auto",
        help="Provider to rewrite hidden threads to. Defaults to auto-detecting the currently visible provider.",
    )
    parser.add_argument("--no-global-state", action="store_true", help="Skip global state pin/title/workspace repairs.")
    parser.add_argument("--no-provider-fix", action="store_true", help="Skip model_provider rewrites for hidden threads.")
    parser.add_argument("--app-name", default="Codex", help="macOS app name to restart. Defaults to Codex.")
    parser.add_argument("--print-json", action="store_true", help="Print the final summary as JSON.")
    return parser.parse_args()


def load_threads(db_path: Path, cwd: str) -> list[ThreadRecord]:
    conn = sqlite3.connect(str(db_path), timeout=30)
    try:
        rows = conn.execute(
            """
            SELECT id, title, cwd, source, model_provider, updated_at
            FROM threads
            WHERE cwd = ? AND archived = 0
            ORDER BY updated_at DESC, id DESC
            """,
            (cwd,),
        ).fetchall()
    finally:
        conn.close()
    return [ThreadRecord(*row) for row in rows]


def run_app_server_requests(cwd: str, codex_home: Path, providers: list[str]) -> dict[str, list[str]]:
    def run_single(model_providers: list[str] | None) -> list[str]:
        env = os.environ.copy()
        env["CODEX_HOME"] = str(codex_home)
        proc = subprocess.Popen(
            ["codex", "app-server", "--listen", "stdio://"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
            env=env,
        )

        request = {
            "jsonrpc": "2.0",
            "id": "2",
            "method": "thread/list",
            "params": {"cwd": cwd, "archived": False, "limit": 200, "sortKey": "updated_at"},
        }
        if model_providers is not None:
            request["params"]["modelProviders"] = model_providers

        try:
            assert proc.stdin is not None
            assert proc.stdout is not None
            proc.stdin.write(
                json.dumps(
                    {
                        "jsonrpc": "2.0",
                        "id": "1",
                        "method": "initialize",
                        "params": {"clientInfo": {"name": "thread-repair", "version": "0"}},
                    },
                    ensure_ascii=False,
                )
                + "\n"
            )
            proc.stdin.write(json.dumps(request, ensure_ascii=False) + "\n")
            proc.stdin.flush()

            deadline = time.time() + 12
            while time.time() < deadline:
                remaining = max(0.1, deadline - time.time())
                ready, _, _ = select.select([proc.stdout], [], [], remaining)
                if not ready:
                    continue
                line = proc.stdout.readline()
                if not line:
                    break
                line = line.strip()
                if not line:
                    continue
                try:
                    payload = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if str(payload.get("id", "")) != "2":
                    continue
                items = payload.get("result", {}).get("data", [])
                return [item.get("id", "") for item in items if item.get("id")]

            stderr = ""
            if proc.stderr is not None:
                try:
                    stderr = proc.stderr.read().strip()
                except Exception:
                    stderr = ""
            suffix = f" {stderr}" if stderr else ""
            raise RuntimeError(f"Timed out waiting for thread/list reply.{suffix}")
        finally:
            if proc.poll() is None:
                proc.terminate()
                try:
                    proc.wait(timeout=2)
                except subprocess.TimeoutExpired:
                    proc.kill()

    results: dict[str, list[str]] = {"default": run_single(None)}
    for provider in providers:
        results[provider] = run_single([provider])
    return results


def parse_thread_titles(node: Any) -> tuple[dict[str, str], list[str]]:
    if isinstance(node, dict) and isinstance(node.get("titles"), dict):
        titles = {key: value for key, value in node["titles"].items() if isinstance(value, str) and value.strip()}
        order = [item for item in node.get("order", []) if isinstance(item, str)]
        return titles, order
    if isinstance(node, dict):
        titles = {key: value for key, value in node.items() if isinstance(value, str) and value.strip()}
        return titles, list(titles.keys())
    return {}, []


def patch_global_state(global_state_path: Path, threads: list[ThreadRecord], cwd: str) -> dict[str, Any]:
    data = json.loads(global_state_path.read_text())
    thread_ids = [thread.thread_id for thread in threads]

    existing_pins = data.get("pinned-thread-ids")
    if not isinstance(existing_pins, list):
        existing_pins = []
    pinned_ids: list[str] = []
    for item in thread_ids + [value for value in existing_pins if isinstance(value, str)]:
        if item not in pinned_ids:
            pinned_ids.append(item)
    data["pinned-thread-ids"] = pinned_ids

    titles, order = parse_thread_titles(data.get("thread-titles"))
    for thread in threads:
        titles[thread.thread_id] = thread.title
    title_order: list[str] = []
    for item in thread_ids + order:
        if item in titles and item not in title_order:
            title_order.append(item)
    data["thread-titles"] = {"titles": titles, "order": title_order}

    hints = data.get("thread-workspace-root-hints")
    if not isinstance(hints, dict):
        hints = {}
    for thread in threads:
        hints[thread.thread_id] = cwd
    data["thread-workspace-root-hints"] = hints

    project_order = data.get("project-order")
    if not isinstance(project_order, list):
        project_order = []
    reordered_projects: list[str] = []
    for item in [cwd] + [value for value in project_order if isinstance(value, str)]:
        if item not in reordered_projects:
            reordered_projects.append(item)
    data["project-order"] = reordered_projects

    saved_roots = data.get("electron-saved-workspace-roots")
    if isinstance(saved_roots, list):
        merged_roots: list[str] = []
        for item in saved_roots + [cwd]:
            if isinstance(item, str) and item not in merged_roots:
                merged_roots.append(item)
        data["electron-saved-workspace-roots"] = merged_roots

    global_state_path.write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")))
    return {
        "pinned_count": len(pinned_ids),
        "title_count": len(data["thread-titles"]["titles"]),
        "workspace_hint_count": len(data["thread-workspace-root-hints"]),
        "project_order_first": data["project-order"][0] if data["project-order"] else None,
    }


def backup_sqlite_live(db_path: Path, backup_path: Path) -> None:
    source = sqlite3.connect(str(db_path), timeout=30)
    dest = sqlite3.connect(str(backup_path), timeout=30)
    try:
        source.backup(dest)
    finally:
        dest.close()
        source.close()


def backup_file(src: Path, dst: Path) -> None:
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)


def choose_target_provider(
    explicit_target: str,
    threads_by_id: dict[str, ThreadRecord],
    default_visible_ids: list[str],
) -> str | None:
    if explicit_target != "auto":
        return explicit_target
    visible_providers = [threads_by_id[thread_id].model_provider for thread_id in default_visible_ids if thread_id in threads_by_id]
    if not visible_providers:
        return None
    return Counter(visible_providers).most_common(1)[0][0]


def rewrite_hidden_providers(db_path: Path, hidden_ids: list[str], target_provider: str) -> int:
    if not hidden_ids:
        return 0
    placeholders = ",".join("?" for _ in hidden_ids)
    conn = sqlite3.connect(str(db_path), timeout=30)
    try:
        cursor = conn.execute(
            f"UPDATE threads SET model_provider = ? WHERE id IN ({placeholders}) AND model_provider <> ?",
            [target_provider, *hidden_ids, target_provider],
        )
        conn.commit()
        return cursor.rowcount
    finally:
        conn.close()


def restart_desktop(app_name: str) -> None:
    subprocess.run(
        [
            "osascript",
            "-e",
            f'tell application "{app_name}" to quit',
            "-e",
            "delay 1",
            "-e",
            f'tell application "{app_name}" to activate',
        ],
        check=True,
    )


def main() -> int:
    args = parse_args()
    cwd = str(Path(args.cwd).resolve())
    codex_home = Path(args.codex_home).expanduser().resolve()
    db_path = codex_home / "state_5.sqlite"
    global_state_path = codex_home / ".codex-global-state.json"

    if not db_path.exists():
        print(f"error: missing db: {db_path}", file=sys.stderr)
        return 2
    if not global_state_path.exists() and not args.no_global_state:
        print(f"error: missing global state: {global_state_path}", file=sys.stderr)
        return 2

    threads = load_threads(db_path, cwd)
    if not threads:
        print(f"error: no non-archived threads found for cwd {cwd}", file=sys.stderr)
        return 3

    threads_by_id = {thread.thread_id: thread for thread in threads}
    providers = sorted({thread.model_provider for thread in threads if thread.model_provider})
    visibility = run_app_server_requests(cwd, codex_home, providers)
    default_visible_ids = visibility.get("default", [])
    all_thread_ids = [thread.thread_id for thread in threads]
    hidden_ids = [thread_id for thread_id in all_thread_ids if thread_id not in set(default_visible_ids)]

    hidden_by_provider: dict[str, list[str]] = defaultdict(list)
    for provider, provider_ids in visibility.items():
        if provider == "default":
            continue
        for thread_id in provider_ids:
            if thread_id in hidden_ids:
                hidden_by_provider[provider].append(thread_id)

    target_provider = choose_target_provider(args.target_provider, threads_by_id, default_visible_ids)
    summary: dict[str, Any] = {
        "cwd": cwd,
        "thread_count": len(threads),
        "providers": providers,
        "default_visible_ids": default_visible_ids,
        "hidden_ids": hidden_ids,
        "hidden_titles": {thread_id: threads_by_id[thread_id].title for thread_id in hidden_ids},
        "provider_visibility": visibility,
        "hidden_by_provider": dict(hidden_by_provider),
        "target_provider": target_provider,
        "applied": False,
        "global_state_changes": None,
        "provider_rows_updated": 0,
        "backup_dir": None,
        "post_apply_visible_ids": None,
    }

    if not args.apply:
        if args.print_json:
            print(json.dumps(summary, ensure_ascii=False, indent=2))
        else:
            print(f"Workspace: {cwd}")
            print(f"Threads in DB: {len(threads)}")
            print(f"Default Desktop-visible threads: {len(default_visible_ids)}")
            print(f"Hidden thread ids: {hidden_ids}")
            print(f"Target provider: {target_provider}")
            if hidden_by_provider:
                print(f"Hidden threads recoverable by provider: {json.dumps(dict(hidden_by_provider), ensure_ascii=False)}")
            print("Dry run only. Re-run with --apply to patch Codex Desktop state.")
        return 0

    timestamp = time.strftime("%Y%m%d_%H%M%S")
    backup_dir = codex_home / "thread_repair_backups" / timestamp
    backup_dir.mkdir(parents=True, exist_ok=True)
    summary["backup_dir"] = str(backup_dir)

    backup_sqlite_live(db_path, backup_dir / "state_5.sqlite")
    if global_state_path.exists():
        backup_file(global_state_path, backup_dir / ".codex-global-state.json")

    if not args.no_global_state:
        summary["global_state_changes"] = patch_global_state(global_state_path, threads, cwd)

    if not args.no_provider_fix and hidden_ids:
        if target_provider is None:
            raise RuntimeError(
                "Could not auto-detect a visible provider for hidden threads. "
                "Re-run with --target-provider <provider>."
            )
        update_ids = hidden_ids
        summary["provider_rows_updated"] = rewrite_hidden_providers(db_path, update_ids, target_provider)

    summary["applied"] = True
    summary["post_apply_visible_ids"] = run_app_server_requests(cwd, codex_home, providers).get("default", [])

    if args.restart_desktop:
        restart_desktop(args.app_name)

    if args.print_json:
        print(json.dumps(summary, ensure_ascii=False, indent=2))
    else:
        print(f"Applied repair for {cwd}")
        print(f"Backups: {backup_dir}")
        if summary["global_state_changes"] is not None:
            print(f"Global state: {json.dumps(summary['global_state_changes'], ensure_ascii=False)}")
        print(f"Provider rows updated: {summary['provider_rows_updated']}")
        print(f"Visible ids after apply: {summary['post_apply_visible_ids']}")
        if args.restart_desktop:
            print(f"Restarted app: {args.app_name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
