from __future__ import annotations

import json
import shutil
import subprocess
from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
from pathlib import Path

from .config import ProjectConfig, load_project_config
from .paths import resolve_raw_dir


CN_TZ = timezone(timedelta(hours=8))


@dataclass(frozen=True)
class BuildResult:
    graphify_used: bool
    graph_path: Path
    report_path: Path
    message: str


def build_graph(root: Path | str = ".", update: bool = False, config: ProjectConfig | None = None) -> BuildResult:
    root_path = Path(root).resolve()
    cfg = config or load_project_config(root_path)
    output_dir = root_path / cfg.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)
    raw_dir = resolve_raw_dir(root_path, cfg)

    if cfg.graphify_mode != "graphify_semantic":
        return write_minimal_graph(
            root_path,
            cfg,
            message=(
                "Codex抽取适配层模式：未调用Graphify语义抽取。"
                "请通过prepare_extraction_tasks/extract_video_keyframes生成Codex任务，"
                "再由Codex写入extraction/results。"
            ),
        )

    graphify = shutil.which("graphify")
    if graphify:
        command = [graphify, str(raw_dir)]
        if update:
            command.append("--update")
        completed = subprocess.run(command, cwd=root_path, check=False, capture_output=True, text=True)
        if completed.returncode != 0:
            return write_minimal_graph(
                root_path,
                cfg,
                message=f"Graphify调用失败，已生成本地最小图谱占位。stderr: {completed.stderr.strip()}",
            )
        graph_path = output_dir / "graph.json"
        report_path = output_dir / "GRAPH_REPORT.md"
        if not graph_path.exists():
            return write_minimal_graph(
                root_path,
                cfg,
                message="Graphify命令已返回成功，但未发现graphify-out/graph.json，已生成本地最小图谱占位。",
            )
        return BuildResult(
            graphify_used=True,
            graph_path=graph_path,
            report_path=report_path,
            message="Graphify编译完成。",
        )

    return write_minimal_graph(root_path, cfg, message="未检测到graphify命令，已生成本地最小图谱占位。")


def write_minimal_graph(root: Path, config: ProjectConfig, message: str) -> BuildResult:
    output_dir = root / config.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)
    graph_path = output_dir / "graph.json"
    report_path = output_dir / "GRAPH_REPORT.md"
    graph = {
        "schema_version": "1.0",
        "generated_by": "tuolinagent",
        "generated_at": datetime.now(CN_TZ).isoformat(timespec="seconds"),
        "compiler": "local-minimal-placeholder",
        "source": config.raw_dir,
        "nodes": [],
        "edges": [],
        "notice": message,
    }
    graph_path.write_text(json.dumps(graph, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    report_path.write_text(
        "\n".join(
            [
                "# GRAPH_REPORT",
                "",
                message,
                "",
                "该文件由tuolinagent在Graphify不可用或调用失败时生成，用于保持Agent知识包生成流程可继续运行。",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    (output_dir / "wiki").mkdir(exist_ok=True)
    (output_dir / "graph.html").write_text("<!doctype html><title>tuolinagent graph placeholder</title>\n", encoding="utf-8")
    return BuildResult(graphify_used=False, graph_path=graph_path, report_path=report_path, message=message)
