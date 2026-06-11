from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path

from .config import ProjectConfig, load_project_config
from .paths import source_path as make_source_path
from .paths import source_to_path


def update_video_pack_keyframes(
    root: Path | str,
    *,
    product: str,
    source_path: str,
    frame_paths: list[str],
    config: ProjectConfig | None = None,
) -> Path:
    root_path = Path(root).resolve()
    cfg = config or load_project_config(root_path)
    pack_path = root_path / cfg.packs_dir / "video" / f"{product}.json"
    payload = json.loads(pack_path.read_text(encoding="utf-8"))
    videos = payload.setdefault("videos", [])
    video = next((item for item in videos if item.get("source_path") == source_path), None)
    if video is None:
        video = {
            "source_path": source_path,
            "duration_seconds": 0,
            "keyframes": [],
            "usable_for": ["product_intro", "application_scene"],
            "prompt_fragments": [],
            "review_notes": [],
        }
        videos.append(video)

    video["keyframes"] = [
        {
            "timestamp": timestamp_from_frame_path(frame_path, index),
            "frame_path": frame_path,
            "visual_description": "",
            "detected_product": product,
            "detected_scene": "",
            "confidence": "pending",
            "review_required": True,
        }
        for index, frame_path in enumerate(frame_paths)
    ]
    pack_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return pack_path


def extract_keyframes_for_video(
    root: Path | str,
    *,
    product: str,
    source_path: str,
    frame_count: int | None = None,
    config: ProjectConfig | None = None,
) -> list[str]:
    root_path = Path(root).resolve()
    cfg = config or load_project_config(root_path)
    video_path = source_to_path(root_path, source_path)
    output_dir = root_path / cfg.output_dir / "cache" / "video-frames"
    output_dir.mkdir(parents=True, exist_ok=True)

    duration = probe_duration(video_path)
    timestamps = choose_timestamps(duration, frame_count or keyframe_count_for_duration(duration))
    frame_paths: list[str] = []
    stem = video_path.stem
    for index, seconds in enumerate(timestamps):
        frame_path = output_dir / f"{stem}_{index:02d}_{int(seconds * 1000):09d}.jpg"
        command = [
            cfg.video_frame_extractor,
            "-y",
            "-ss",
            str(seconds),
            "-i",
            str(video_path),
            "-frames:v",
            "1",
            str(frame_path),
        ]
        subprocess.run(command, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        frame_paths.append(make_source_path(root_path, frame_path))

    update_video_pack_keyframes(
        root_path,
        product=product,
        source_path=source_path,
        frame_paths=frame_paths,
        config=cfg,
    )
    return frame_paths


def probe_duration(video_path: Path) -> float:
    command = [
        "ffprobe",
        "-v",
        "error",
        "-show_entries",
        "format=duration",
        "-of",
        "default=noprint_wrappers=1:nokey=1",
        str(video_path),
    ]
    completed = subprocess.run(command, check=True, capture_output=True, text=True)
    return max(float(completed.stdout.strip() or "0"), 1.0)


def choose_timestamps(duration: float, frame_count: int) -> list[float]:
    count = max(3, min(frame_count, 8))
    if count == 3:
        return [0.0, max(duration / 2, 0.1), max(duration - 0.1, 0.1)]
    step = duration / (count - 1)
    return [min(index * step, max(duration - 0.1, 0.1)) for index in range(count)]


def keyframe_count_for_duration(duration: float) -> int:
    if duration <= 10:
        return 3
    if duration <= 30:
        return 5
    return 8


def timestamp_from_frame_path(frame_path: str, index: int) -> str:
    millis_match = re.search(r"_(\d{2})_(\d{9})\.", frame_path)
    if millis_match:
        seconds = int(millis_match.group(2)) / 1000
        return format_timestamp(seconds)
    match = re.search(r"_(\d{6})\.", frame_path)
    seconds = int(match.group(1)) if match else index
    return format_timestamp(seconds)


def format_timestamp(seconds: float) -> str:
    whole_seconds = int(seconds)
    return f"{whole_seconds // 3600:02d}:{whole_seconds % 3600 // 60:02d}:{whole_seconds % 60:02d}"
