#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from tuolin_kb.config import load_project_config
from tuolin_kb.extraction import create_extraction_tasks, write_pending_extraction_tasks
from tuolin_kb.video import extract_keyframes_for_video


def main() -> int:
    root = Path(".").resolve()
    config = load_project_config(root)
    video_dir = root / config.packs_dir / "video"
    extracted = 0
    failures: list[str] = []

    for pack_path in sorted(video_dir.glob("*.json")):
        pack = json.loads(pack_path.read_text(encoding="utf-8"))
        product = pack["product"]
        for video in pack.get("videos", []):
            source_path = video.get("source_path", "")
            if not source_path:
                continue
            try:
                frames = extract_keyframes_for_video(
                    root,
                    product=product,
                    source_path=source_path,
                    config=config,
                )
                extracted += len(frames)
                print(f"{product}: {source_path} -> {len(frames)} frames")
            except Exception as exc:  # noqa: BLE001 - report per-file failure and continue
                failures.append(f"{product}: {source_path}: {exc}")

    task_path = write_pending_extraction_tasks(root, create_extraction_tasks(root, config), config=config)
    print(f"关键帧数量: {extracted}")
    print(f"素材分析清单: {task_path}")
    if failures:
        print("失败项:")
        for item in failures:
            print(f"- {item}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
