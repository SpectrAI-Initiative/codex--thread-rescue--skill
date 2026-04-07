#!/usr/bin/env python3

from __future__ import annotations

import sys
from pathlib import Path
from typing import Iterable

try:
    from PIL import Image, ImageColor, ImageDraw, ImageFilter, ImageFont
except ModuleNotFoundError as exc:
    if exc.name == "PIL":
        print("[FAIL] Pillow is required to regenerate the README walkthrough visuals.")
        print("[INFO] Install it with: python3 -m pip install Pillow")
        raise SystemExit(1)
    raise


WIDTH = 1600
HEIGHT = 980
OUTPUT_DIR = Path(__file__).resolve().parents[1] / "assets" / "readme"


def rgba(value: str, alpha: int = 255) -> tuple[int, int, int, int]:
    r, g, b = ImageColor.getrgb(value)
    return (r, g, b, alpha)


def load_font(size: int, mono: bool = False) -> ImageFont.FreeTypeFont:
    candidates = [
        ("/System/Library/Fonts/Menlo.ttc", 0) if mono else ("/System/Library/Fonts/SFNS.ttf", 0),
        ("/System/Library/Fonts/Monaco.ttf", 0) if mono else ("/System/Library/Fonts/Helvetica.ttc", 0),
    ]
    for path, index in candidates:
        try:
            return ImageFont.truetype(path, size=size, index=index)
        except OSError:
            continue
    return ImageFont.load_default()


FONT_H1 = load_font(62)
FONT_H2 = load_font(28)
FONT_BODY = load_font(24)
FONT_SMALL = load_font(20)
FONT_CODE = load_font(23, mono=True)
FONT_CODE_SMALL = load_font(20, mono=True)


def create_canvas() -> Image.Image:
    img = Image.new("RGBA", (WIDTH, HEIGHT), rgba("#07111e"))
    draw = ImageDraw.Draw(img)

    top = rgba("#08131f")
    bottom = rgba("#0f3d3e")
    for y in range(HEIGHT):
        t = y / max(HEIGHT - 1, 1)
        color = tuple(int(top[i] * (1 - t) + bottom[i] * t) for i in range(4))
        draw.line([(0, y), (WIDTH, y)], fill=color, width=1)

    for x in range(0, WIDTH, 44):
        draw.line([(x, 0), (x, HEIGHT)], fill=rgba("#9fd3ff", 16), width=1)
    for y in range(0, HEIGHT, 44):
        draw.line([(0, y), (WIDTH, y)], fill=rgba("#9fd3ff", 12), width=1)

    glow = Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, 0))
    glow_draw = ImageDraw.Draw(glow)
    glow_draw.ellipse((1060, 20, 1560, 520), fill=rgba("#7ff2c4", 52))
    glow_draw.ellipse((980, 520, 1540, 1080), fill=rgba("#64c4ff", 48))
    glow = glow.filter(ImageFilter.GaussianBlur(80))
    img.alpha_composite(glow)

    return img


def draw_shadow(base: Image.Image, box: tuple[int, int, int, int], radius: int = 26, alpha: int = 82) -> None:
    shadow = Image.new("RGBA", base.size, (0, 0, 0, 0))
    sdraw = ImageDraw.Draw(shadow)
    x1, y1, x2, y2 = box
    sdraw.rounded_rectangle((x1 + 10, y1 + 18, x2 + 10, y2 + 18), radius=28, fill=(0, 0, 0, alpha))
    shadow = shadow.filter(ImageFilter.GaussianBlur(radius))
    base.alpha_composite(shadow)


def draw_chip(draw: ImageDraw.ImageDraw, xy: tuple[int, int], text: str, fill: str, stroke: str, text_fill: str) -> None:
    x, y = xy
    bbox = draw.textbbox((0, 0), text, font=FONT_SMALL)
    width = bbox[2] - bbox[0] + 34
    height = 42
    draw.rounded_rectangle((x, y, x + width, y + height), radius=21, fill=rgba(fill, 255), outline=rgba(stroke, 180), width=2)
    draw.text((x + 17, y + 9), text, font=FONT_SMALL, fill=rgba(text_fill))


def draw_header(draw: ImageDraw.ImageDraw, step: str, title: str, subtitle: str) -> None:
    draw_chip(draw, (92, 68), step, "#0d2535", "#64c4ff", "#eaf7ff")
    draw.text((92, 132), title, font=FONT_H1, fill=rgba("#f4f8fb"))
    draw.text((92, 204), subtitle, font=FONT_H2, fill=rgba("#b9d8ea"))


def draw_window(base: Image.Image, title: str) -> tuple[ImageDraw.ImageDraw, tuple[int, int, int, int]]:
    box = (82, 278, 1518, 884)
    draw_shadow(base, box)
    draw = ImageDraw.Draw(base)
    draw.rounded_rectangle(box, radius=32, fill=rgba("#081723", 245), outline=rgba("#7fb6d5", 90), width=2)
    draw.rounded_rectangle((82, 278, 1518, 346), radius=32, fill=rgba("#0d2030", 255))
    draw.rectangle((82, 314, 1518, 346), fill=rgba("#0d2030", 255))

    for idx, color in enumerate(["#f86d6d", "#fbb64a", "#62d07f"]):
        draw.ellipse((114 + idx * 30, 300, 132 + idx * 30, 318), fill=rgba(color))

    draw.text((180, 297), title, font=FONT_BODY, fill=rgba("#dff3ff"))
    return draw, box


def draw_sidebar(draw: ImageDraw.ImageDraw, box: tuple[int, int, int, int], items: Iterable[dict[str, str]], muted: bool = False, restored: bool = False) -> None:
    x1, y1, x2, y2 = box
    sidebar_x2 = x1 + 330
    draw.rectangle((x1, y1, sidebar_x2, y2), fill=rgba("#091a28", 240))
    draw.rectangle((sidebar_x2, y1, sidebar_x2 + 1, y2), fill=rgba("#27485d", 120))

    draw.text((x1 + 28, y1 + 28), "Projects", font=FONT_SMALL, fill=rgba("#8fb6ca"))
    draw.text((x1 + 28, y1 + 64), "VIPER-R1 / VIPER_R1_ori", font=FONT_BODY, fill=rgba("#eaf7ff"))
    draw_chip(draw, (x1 + 28, y1 + 104), "Codex Desktop", "#0b2732", "#4dd1a8", "#d9fff0")

    y = y1 + 168
    for item in items:
        accent = item.get("accent", "#27485d")
        fill = "#0c2231" if restored else "#0b1d2a"
        if muted:
            fill = "#0b1620"
            accent = "#6d5561"
        draw.rounded_rectangle((x1 + 22, y, sidebar_x2 - 22, y + 78), radius=20, fill=rgba(fill, 245), outline=rgba(accent, 180), width=2)
        draw.text((x1 + 42, y + 16), item["title"], font=FONT_BODY, fill=rgba("#dff2ff", 215 if muted else 255))
        draw.text((x1 + 42, y + 46), item["meta"], font=FONT_SMALL, fill=rgba("#87a8ba", 170 if muted else 230))
        if item.get("pill"):
            pill_text = item["pill"]
            pb = draw.textbbox((0, 0), pill_text, font=FONT_SMALL)
            pw = pb[2] - pb[0] + 22
            draw.rounded_rectangle((sidebar_x2 - 22 - pw, y + 18, sidebar_x2 - 22, y + 52), radius=17, fill=rgba("#102937"), outline=rgba("#4cd6b0", 120), width=2)
            draw.text((sidebar_x2 - 11 - pw, y + 24), pill_text, font=FONT_SMALL, fill=rgba("#d5fff3"))
        y += 92


def draw_callout(draw: ImageDraw.ImageDraw, box: tuple[int, int, int, int], title: str, body: str, accent: str, success: bool = False) -> None:
    x1, y1, x2, y2 = box
    draw.rounded_rectangle(box, radius=28, fill=rgba("#0d2230", 250), outline=rgba(accent, 210), width=2)
    draw.text((x1 + 28, y1 + 22), title, font=FONT_H2, fill=rgba("#f4f8fb"))
    body_fill = "#d3e7f5" if not success else "#d8fff1"
    draw.multiline_text((x1 + 28, y1 + 72), body, font=FONT_BODY, fill=rgba(body_fill), spacing=10)


def before_image() -> Image.Image:
    img = create_canvas()
    draw = ImageDraw.Draw(img)
    draw_header(draw, "Step 1", "Before Repair", "Old workspace threads still exist on disk, but the Desktop sidebar stays incomplete.")
    draw, box = draw_window(img, "Codex Desktop · Workspace thread list")

    sidebar_items = [
        {"title": "Today", "meta": "Only the newest threads show up", "pill": "partial"},
        {"title": "Open deeplink", "meta": "Thread opens weakly or not at all", "pill": "flaky"},
        {"title": "Older runs", "meta": "Still present in state_5.sqlite", "pill": "hidden"},
    ]
    draw_sidebar(draw, (box[0], box[1] + 68, box[2], box[3]), sidebar_items, muted=True)

    main_x1 = box[0] + 360
    draw_callout(
        draw,
        (main_x1, box[1] + 104, box[2] - 42, box[1] + 268),
        "Typical failure mode",
        "The repo still has local thread rows, but Desktop default visibility does not\nsurface them in the left sidebar. Deeplink behavior may also feel broken.",
        "#f391a4",
    )
    draw_chip(draw, (main_x1, box[1] + 294), "state_5.sqlite still has 10 threads", "#23141e", "#f391a4", "#ffe4ec")
    draw_chip(draw, (main_x1 + 374, box[1] + 294), "sidebar visibility is incomplete", "#1b2330", "#7fa9c5", "#e4f5ff")

    draw.rounded_rectangle((main_x1, box[1] + 360, box[2] - 42, box[3] - 24), radius=28, fill=rgba("#091825", 255), outline=rgba("#2d5269", 160), width=2)
    draw.text((main_x1 + 28, box[1] + 390), "What users usually notice", font=FONT_H2, fill=rgba("#f5f8fb"))
    bullets = [
        "Old project threads do not repopulate in the sidebar",
        "codex://threads/<id> deeplinks do nothing or feel inconsistent",
        "thread/read can still work by ID even though Desktop thread/list is incomplete",
    ]
    y = box[1] + 432
    for bullet in bullets:
        draw.ellipse((main_x1 + 32, y + 10, main_x1 + 42, y + 20), fill=rgba("#7ff2c4"))
        draw.text((main_x1 + 58, y), bullet, font=FONT_BODY, fill=rgba("#d4e6f4"))
        y += 48

    return img


def invoke_image() -> Image.Image:
    img = create_canvas()
    draw = ImageDraw.Draw(img)
    draw_header(draw, "Step 2", "Run the Skill", "Start with a dry run from Codex or the bundled script, then inspect the summary before applying.")
    draw, box = draw_window(img, "Codex Thread Rescue · Prompt + CLI")

    left = (box[0] + 34, box[1] + 96, box[0] + 710, box[3] - 40)
    right = (box[0] + 744, box[1] + 96, box[2] - 34, box[3] - 40)

    draw.rounded_rectangle(left, radius=28, fill=rgba("#0b1d2a", 255), outline=rgba("#4dd1a8", 170), width=2)
    draw.text((left[0] + 28, left[1] + 24), "Ask Codex directly", font=FONT_H2, fill=rgba("#f4f8fb"))
    prompt_lines = [
        "Use $codex--thread-rescue--skill",
        "to restore missing local Codex Desktop threads",
        "for /absolute/path/to/project.",
    ]
    y = left[1] + 90
    for line in prompt_lines:
        draw.rounded_rectangle((left[0] + 28, y, left[2] - 28, y + 58), radius=18, fill=rgba("#112737"), outline=rgba("#69dfbb", 140), width=2)
        draw.text((left[0] + 46, y + 16), line, font=FONT_CODE_SMALL, fill=rgba("#dffdf2"))
        y += 74
    draw_chip(draw, (left[0] + 28, left[1] + 344), "Codex path", "#103026", "#4dd1a8", "#dbfff1")
    draw_chip(draw, (left[0] + 182, left[1] + 344), "natural language trigger", "#122235", "#7cb2d2", "#e5f5ff")

    draw.rounded_rectangle(right, radius=28, fill=rgba("#091722", 255), outline=rgba("#67a6c9", 150), width=2)
    draw.text((right[0] + 28, right[1] + 24), "Or run the script manually", font=FONT_H2, fill=rgba("#f4f8fb"))
    code_lines = [
        "$ python3 scripts/repair_codex_desktop_threads.py \\",
        "    --cwd /absolute/path/to/project --print-json",
        "",
        "{",
        '  "thread_count": 10,',
        '  "hidden_ids": ["…"],',
        '  "target_provider": "rustcat",',
        '  "applied": false',
        "}",
    ]
    y = right[1] + 86
    for line in code_lines:
        color = "#d7f0ff" if not line.startswith("  ") and not line.startswith("{") and not line.startswith("}") else "#8bc1dc"
        if line.startswith("$"):
            color = "#c9ffe9"
        draw.text((right[0] + 28, y), line, font=FONT_CODE_SMALL, fill=rgba(color))
        y += 38
    draw_chip(draw, (right[0] + 28, right[1] + 346), "Dry-run first", "#211a11", "#fbb64a", "#fff1cf")
    draw_chip(draw, (right[0] + 178, right[1] + 346), "Backups before writes", "#162134", "#7ca8d8", "#e4f5ff")
    draw_chip(draw, (right[0] + 410, right[1] + 346), "Inspect JSON summary", "#0f2b2f", "#64c4ff", "#dcfbff")

    return img


def after_image() -> Image.Image:
    img = create_canvas()
    draw = ImageDraw.Draw(img)
    draw_header(draw, "Step 3", "After Repair", "The sidebar is repopulated, workspace hints are aligned, and Desktop thread navigation becomes consistent again.")
    draw, box = draw_window(img, "Codex Desktop · Recovered workspace threads")

    sidebar_items = [
        {"title": "Repair hidden threads", "meta": "now visible · 2 min ago", "pill": "restored", "accent": "#4dd1a8"},
        {"title": "Expand coverage", "meta": "smoke test · 8 min ago", "pill": "visible", "accent": "#64c4ff"},
        {"title": "Investigate provider filter", "meta": "analysis · 14 min ago", "pill": "visible", "accent": "#64c4ff"},
        {"title": "Patch pinned metadata", "meta": "workspace hints · 21 min ago", "pill": "visible", "accent": "#64c4ff"},
        {"title": "Open deeplink again", "meta": "navigation stable", "pill": "ok", "accent": "#4dd1a8"},
    ]
    draw_sidebar(draw, (box[0], box[1] + 68, box[2], box[3]), sidebar_items, restored=True)

    main_x1 = box[0] + 360
    draw_callout(
        draw,
        (main_x1, box[1] + 104, box[2] - 42, box[1] + 284),
        "What improves",
        "Missing repo threads show up again in the left sidebar.\nWorkspace pinning, title metadata, and deeplink behavior are restored.",
        "#4dd1a8",
        success=True,
    )
    draw_chip(draw, (main_x1, box[1] + 312), "10 threads visible again", "#0d2c24", "#4dd1a8", "#dcfff2")
    draw_chip(draw, (main_x1 + 270, box[1] + 312), "workspace hints synced", "#112735", "#7fa9c5", "#e4f5ff")
    draw_chip(draw, (main_x1 + 522, box[1] + 312), "deeplinks behave normally", "#112735", "#7fa9c5", "#e4f5ff")

    draw.rounded_rectangle((main_x1, box[1] + 380, box[2] - 42, box[3] - 24), radius=28, fill=rgba("#091825", 255), outline=rgba("#2d5269", 160), width=2)
    draw.text((main_x1 + 28, box[1] + 410), "Why the fix works", font=FONT_H2, fill=rgba("#f5f8fb"))
    bullets = [
        "Desktop global state is patched so the project is pinned and workspace-root hinted",
        "Hidden thread rows can be rewritten to the visible model provider when filtering is the blocker",
        "You can still keep the operation cautious: dry-run, inspect JSON, then apply",
    ]
    y = box[1] + 452
    for bullet in bullets:
        draw.ellipse((main_x1 + 32, y + 10, main_x1 + 42, y + 20), fill=rgba("#7ff2c4"))
        draw.text((main_x1 + 58, y), bullet, font=FONT_BODY, fill=rgba("#d4e6f4"))
        y += 48

    return img


def save_gif(frames: list[Image.Image], path: Path) -> None:
    durations = []
    animation_frames: list[Image.Image] = []
    for index, frame in enumerate(frames):
        animation_frames.append(frame.convert("P", palette=Image.ADAPTIVE))
        durations.append(950 if index < len(frames) - 1 else 1300)
        if index < len(frames) - 1:
            nxt = frames[index + 1]
            for alpha in [0.25, 0.5, 0.75]:
                blended = Image.blend(frame, nxt, alpha).convert("P", palette=Image.ADAPTIVE)
                animation_frames.append(blended)
                durations.append(180)

    animation_frames[0].save(
        path,
        save_all=True,
        append_images=animation_frames[1:],
        duration=durations,
        loop=0,
        optimize=False,
        disposal=2,
    )


def main() -> int:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    before = before_image()
    invoke = invoke_image()
    after = after_image()

    before.save(OUTPUT_DIR / "thread-rescue-before.png")
    invoke.save(OUTPUT_DIR / "thread-rescue-invoke.png")
    after.save(OUTPUT_DIR / "thread-rescue-after.png")
    save_gif([before, invoke, after], OUTPUT_DIR / "thread-rescue-demo.gif")

    print(f"[OK] Wrote README visuals to {OUTPUT_DIR}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
