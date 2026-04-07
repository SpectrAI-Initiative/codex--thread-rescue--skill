#!/usr/bin/env python3

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path


FRONTMATTER_PATTERN = re.compile(r"^---\n(.*?)\n---\n", re.DOTALL)
FIELD_PATTERN = re.compile(r"^([A-Za-z0-9_]+):\s*(.+?)\s*$")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Validate the packaged Codex skill metadata and smoke-test bundled scripts.",
    )
    parser.add_argument(
        "--repo-root",
        default=str(Path(__file__).resolve().parents[1]),
        help="Skill repository root. Defaults to the parent of this script.",
    )
    return parser.parse_args()


def fail(message: str) -> None:
    print(f"[FAIL] {message}")
    raise SystemExit(1)


def parse_skill_frontmatter(skill_path: Path) -> dict[str, str]:
    content = skill_path.read_text()
    match = FRONTMATTER_PATTERN.match(content)
    if not match:
        fail(f"{skill_path} is missing a valid YAML-style frontmatter block")

    result: dict[str, str] = {}
    for line in match.group(1).splitlines():
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        result[key.strip()] = value.strip()
    return result


def parse_openai_yaml(yaml_path: Path) -> dict[str, dict[str, str]]:
    sections: dict[str, dict[str, str]] = {}
    current_section: str | None = None

    for raw_line in yaml_path.read_text().splitlines():
        if not raw_line.strip():
            continue
        if not raw_line.startswith(" "):
            if not raw_line.endswith(":"):
                fail(f"{yaml_path} has an invalid top-level line: {raw_line}")
            current_section = raw_line[:-1]
            sections[current_section] = {}
            continue

        if current_section is None:
            fail(f"{yaml_path} has indented fields before a top-level section")

        match = FIELD_PATTERN.match(raw_line.strip())
        if not match:
            fail(f"{yaml_path} has an invalid field line: {raw_line}")
        key, value = match.groups()
        if value.startswith('"') and value.endswith('"'):
            value = value[1:-1]
        sections[current_section][key] = value

    return sections


def require_file(path: Path) -> None:
    if not path.is_file():
        fail(f"Required file is missing: {path}")


def run_help(command: list[str], cwd: Path) -> None:
    result = subprocess.run(command, cwd=str(cwd), capture_output=True, text=True)
    if result.returncode != 0:
        details = result.stderr.strip() or result.stdout.strip()
        fail(f"Command failed: {' '.join(command)}\n{details}")


def main() -> int:
    args = parse_args()
    repo_root = Path(args.repo_root).resolve()

    skill_path = repo_root / "SKILL.md"
    readme_path = repo_root / "README.md"
    openai_path = repo_root / "agents" / "openai.yaml"
    install_script = repo_root / "scripts" / "install_skill.py"
    repair_script = repo_root / "scripts" / "repair_codex_desktop_threads.py"
    banner_path = repo_root / "assets" / "codex-thread-rescue-banner.svg"
    icon_path = repo_root / "assets" / "codex-thread-rescue-icon.svg"
    logo_path = repo_root / "assets" / "codex-thread-rescue-logo.svg"

    for path in [skill_path, readme_path, openai_path, install_script, repair_script, banner_path, icon_path, logo_path]:
        require_file(path)

    frontmatter = parse_skill_frontmatter(skill_path)
    if frontmatter.get("name") != "codex--thread-rescue--skill":
        fail("SKILL.md frontmatter name must be codex--thread-rescue--skill")
    if "description" not in frontmatter or len(frontmatter["description"]) < 40:
        fail("SKILL.md frontmatter description is missing or too short")

    readme_text = readme_path.read_text()
    for needle in [
        "$codex--thread-rescue--skill",
        "scripts/install_skill.py",
        "## FAQ",
        "## Quick start",
    ]:
        if needle not in readme_text:
            fail(f"README.md is missing expected content: {needle}")

    sections = parse_openai_yaml(openai_path)
    interface = sections.get("interface", {})
    policy = sections.get("policy", {})

    required_interface = {
        "display_name": "Codex Thread Rescue",
        "short_description": "Bring back missing Codex Desktop threads",
        "icon_small": "./assets/codex-thread-rescue-icon.svg",
        "icon_large": "./assets/codex-thread-rescue-logo.svg",
        "brand_color": "#7FF2C4",
    }
    for key, expected in required_interface.items():
        if interface.get(key) != expected:
            fail(f"agents/openai.yaml interface.{key} must be {expected!r}")

    default_prompt = interface.get("default_prompt", "")
    if "$codex--thread-rescue--skill" not in default_prompt:
        fail("agents/openai.yaml default_prompt must mention $codex--thread-rescue--skill")
    if policy.get("allow_implicit_invocation") != "true":
        fail("agents/openai.yaml policy.allow_implicit_invocation must be true")

    run_help(["python3", str(install_script), "--help"], repo_root)
    run_help(["python3", str(repair_script), "--help"], repo_root)

    print("[OK] Skill metadata and bundled scripts validated successfully.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
