from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class ProjectConfig:
    raw_dir: str = "raw"
    output_dir: str = "graphify-out"
    packs_dir: str = "graphify-out/tuolin-agent-packs"
    graphify_mode: str = "codex_adapter"
    mineru_enabled: bool = True
    mineru_command: str = "mineru"
    mineru_backend: str = "pipeline"
    mineru_lang: str = "ch"
    mineru_cache_dir: str = "graphify-out/cache/mineru"
    default_vision_model: str = "gpt-5.5"
    escalation_vision_model: str = "gpt-5.5-pro"
    video_frame_extractor: str = "ffmpeg"
    video_input_mode: str = "ffmpeg_keyframes"
    model_switch_surface: str = "config_only"


def load_project_config(root: Path | str = ".") -> ProjectConfig:
    root_path = Path(root)
    config_path = root_path / "config" / "tuolin-kb.config.json"
    model_path = root_path / "config" / "model-policy.json"

    payload: dict[str, Any] = {}
    if config_path.exists():
        payload.update(json.loads(config_path.read_text(encoding="utf-8")))
    if model_path.exists():
        payload.update(json.loads(model_path.read_text(encoding="utf-8")))

    allowed = {field for field in ProjectConfig.__dataclass_fields__}
    return ProjectConfig(**{key: value for key, value in payload.items() if key in allowed})
