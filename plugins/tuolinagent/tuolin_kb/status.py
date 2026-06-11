from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from .build_partitions import refresh_manifest_build_partitions
from .config import ProjectConfig, load_project_config


@dataclass(frozen=True)
class StatusReport:
    manifest_path: Path
    build_partitions: list[dict]
    products: list[dict]
    pending_extraction_count: int = 0
    pending_result_count: int = 0
    review_claim_count: int = 0


def load_status(root: Path | str = ".", config: ProjectConfig | None = None) -> StatusReport:
    root_path = Path(root).resolve()
    cfg = config or load_project_config(root_path)
    refresh_manifest_build_partitions(root_path, cfg)
    manifest_path = root_path / cfg.packs_dir / "manifest.json"
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    build_partitions = payload.get("build_partitions", [])
    return StatusReport(
        manifest_path=manifest_path,
        build_partitions=build_partitions,
        products=payload.get("products", []),
        pending_extraction_count=sum(item.get("pending_extraction_count", 0) for item in build_partitions),
        pending_result_count=sum(item.get("pending_result_count", 0) for item in build_partitions),
        review_claim_count=sum(item.get("review_claim_count", 0) for item in build_partitions),
    )


def format_status(report: StatusReport) -> str:
    lines = [
        f"知识库状态：{report.manifest_path}",
        f"待分析素材：{report.pending_extraction_count}",
        f"待应用分析结果：{report.pending_result_count}",
        f"待复核：{report.review_claim_count}",
        "",
        "构建分区：",
    ]
    for item in report.build_partitions:
        lines.append(
            f"- {item['name']}：{item['status']}（{item['status_label']}），"
            f"待分析 {item.get('pending_extraction_count', 0)}，"
            f"待应用 {item.get('pending_result_count', 0)}，"
            f"待复核 {item.get('review_claim_count', 0)}"
        )
    lines.extend(["", "产品："])
    for item in report.products:
        variants = item.get("variants") or []
        variant_text = f"；变体：{'、'.join(variants)}" if variants else ""
        lines.append(
            f"- {item['name']}：{item['status']}（{item['status_label']}），"
            f"{item['asset_status']}（{item['asset_status_label']}）{variant_text}"
        )
    return "\n".join(lines)
