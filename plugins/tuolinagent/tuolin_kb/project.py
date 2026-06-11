from __future__ import annotations

import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

from .config import ProjectConfig, load_project_config
from .document_conversion import resolve_command
from .paths import resolve_output_dir, resolve_packs_dir, resolve_raw_dir


@dataclass(frozen=True)
class ProjectReport:
    root: Path
    raw_path: Path
    output_path: Path
    packs_path: Path
    raw_exists: bool
    core_knowledge_exists: bool
    core_knowledge_file_count: int
    graphify_available: bool
    ffmpeg_available: bool
    mineru_available: bool
    python_version: str
    graphify_out_ignored: bool
    warnings: tuple[str, ...] = field(default_factory=tuple)

    @property
    def ok(self) -> bool:
        return self.raw_exists and self.core_knowledge_exists


def validate_project(root: Path | str = ".", config: ProjectConfig | None = None) -> ProjectReport:
    root_path = Path(root).resolve()
    cfg = config or load_project_config(root_path)
    raw_path = resolve_raw_dir(root_path, cfg)
    output_path = resolve_output_dir(root_path, cfg)
    packs_path = resolve_packs_dir(root_path, cfg)
    core_path = raw_path / "00_知识库核心资料"
    core_files = [
        path
        for path in core_path.glob("*")
        if path.is_file() and path.name != ".DS_Store" and not path.name.startswith("~")
    ] if core_path.exists() else []

    warnings: list[str] = []
    if not raw_path.exists():
        warnings.append("缺少 raw/ 目录。")
    if not core_path.exists():
        warnings.append("缺少 raw/00_知识库核心资料/ 目录。")
    if Path(cfg.raw_dir).is_absolute() and not Path(cfg.output_dir).is_absolute():
        warnings.append("raw_dir 是绝对路径，但 output_dir 是相对路径；建议改成绝对路径，避免在不同项目目录生成多个 graphify-out。")
    if Path(cfg.raw_dir).is_absolute() and not Path(cfg.packs_dir).is_absolute():
        warnings.append("raw_dir 是绝对路径，但 packs_dir 是相对路径；建议改成 output_dir 下的绝对路径，避免读取错知识包。")

    graphify_out_ignored = _git_ignores(root_path, cfg.output_dir)
    if not graphify_out_ignored:
        warnings.append("graphify-out/ 尚未被 git 忽略。")

    if shutil.which("graphify") is None:
        warnings.append("未检测到 graphify 命令；build 会使用本地最小图谱占位输出。")
    if shutil.which(cfg.video_frame_extractor) is None:
        warnings.append(f"未检测到 {cfg.video_frame_extractor}；视频关键帧提取不可用。")
    mineru_available = resolve_command(cfg.mineru_command) is not None
    if cfg.mineru_enabled and not mineru_available:
        warnings.append(f"未检测到 {cfg.mineru_command}；PDF正文无法自动转换成Markdown。")

    return ProjectReport(
        root=root_path,
        raw_path=raw_path,
        output_path=output_path,
        packs_path=packs_path,
        raw_exists=raw_path.exists(),
        core_knowledge_exists=core_path.exists(),
        core_knowledge_file_count=len(core_files),
        graphify_available=shutil.which("graphify") is not None,
        ffmpeg_available=shutil.which(cfg.video_frame_extractor) is not None,
        mineru_available=mineru_available,
        python_version=sys.version.split()[0],
        graphify_out_ignored=graphify_out_ignored,
        warnings=tuple(warnings),
    )


def _git_ignores(root: Path, path: str) -> bool:
    path_obj = Path(path)
    if path_obj.is_absolute():
        try:
            path = path_obj.resolve().relative_to(root.resolve()).as_posix()
        except ValueError:
            return True
    git_dir = root / ".git"
    gitignore = root / ".gitignore"
    if not git_dir.exists():
        if not gitignore.exists():
            return False
        lines = gitignore.read_text(encoding="utf-8").splitlines()
        normalized = path.rstrip("/") + "/"
        return normalized in {line.strip() for line in lines}

    try:
        result = subprocess.run(
            ["git", "check-ignore", "-q", path],
            cwd=root,
            check=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except OSError:
        return False
    return result.returncode == 0
