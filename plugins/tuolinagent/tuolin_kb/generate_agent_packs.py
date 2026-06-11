from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any

from .build_partitions import build_partitions_manifest
from .config import ProjectConfig, load_project_config
from .constants import ASSET_STATUS_LABELS, PACK_DIRECTORIES, STATUS_LABELS
from .document_conversion import ensure_pdf_markdown_sources
from .domain_packs import generate_domain_packs
from .local_graph import write_local_graph_outputs
from .products import ProductKnowledge, collect_product_knowledge


CN_TZ = timezone(timedelta(hours=8))


@dataclass(frozen=True)
class AgentPackOutput:
    packs_dir: Path
    manifest_path: Path
    product_count: int


def generate_agent_packs(root: Path | str = ".", config: ProjectConfig | None = None) -> AgentPackOutput:
    root_path = Path(root).resolve()
    cfg = config or load_project_config(root_path)
    packs_dir = root_path / cfg.packs_dir
    ensure_pdf_markdown_sources(root_path, cfg)
    for dirname in [
        "products",
        "competitors",
        "content",
        "video",
        "evidence",
        "readable",
        "company",
        "standards",
        "market",
    ]:
        (packs_dir / dirname).mkdir(parents=True, exist_ok=True)

    product_knowledge = collect_product_knowledge(root_path, cfg)
    for knowledge in product_knowledge:
        if knowledge.status == "not_built":
            remove_product_packs(packs_dir, knowledge.product.name)
        else:
            write_product_packs(packs_dir, knowledge, cfg)

    generate_domain_packs(root_path, cfg)
    manifest = build_manifest(root_path, cfg, product_knowledge)
    manifest_path = packs_dir / "manifest.json"
    write_json(manifest_path, manifest)
    write_local_graph_outputs(root_path, cfg)
    write_json(manifest_path, build_manifest(root_path, cfg, product_knowledge))

    return AgentPackOutput(packs_dir=packs_dir, manifest_path=manifest_path, product_count=len(product_knowledge))


def build_manifest(root: Path, config: ProjectConfig, products: list[ProductKnowledge]) -> dict[str, Any]:
    graph_path = root / config.output_dir / "graph.json"
    return {
        "schema_version": "1.0",
        "generated_at": datetime.now(CN_TZ).isoformat(timespec="seconds"),
        "generated_by": "tuolinagent",
        "graphify_output": {
            "path": f"{config.output_dir}/graph.json",
            "hash": sha256_file(graph_path) if graph_path.exists() else None,
            "exists": graph_path.exists(),
        },
        "products": [manifest_product_item(item) for item in products],
        "build_partitions": build_partitions_manifest(root, config, products),
    }


def manifest_product_item(knowledge: ProductKnowledge) -> dict[str, Any]:
    name = knowledge.product.name
    packs = {
        "product_pack": f"products/{name}.json",
        "competitor_pack": f"competitors/{name}.json",
        "content_pack": f"content/{name}.json",
        "video_pack": f"video/{name}.json",
        "evidence_pack": f"evidence/{name}.json",
        "readable": f"readable/{name}.md",
    }
    return {
        "name": name,
        "slug": knowledge.product.slug,
        "status": knowledge.status,
        "status_label": STATUS_LABELS.get(knowledge.status, knowledge.status),
        "asset_status": knowledge.asset_status,
        "asset_status_label": ASSET_STATUS_LABELS.get(knowledge.asset_status, knowledge.asset_status),
        "review_required": knowledge.review_required,
        "variants": list(knowledge.product.variants),
        "packs": {} if knowledge.status == "not_built" else packs,
    }


def write_product_packs(packs_dir: Path, knowledge: ProductKnowledge, config: ProjectConfig) -> None:
    product = knowledge.product.name
    common = {
        "schema_version": "1.0",
        "generated_by": "tuolinagent",
        "product": product,
        "status": knowledge.status,
        "asset_status": knowledge.asset_status,
    }
    facts = {
        **common,
        "confidence": "confirmed",
        "facts": {
            **knowledge.facts,
            "检测报告路径": list(knowledge.assets.reports),
            "检测报告正文路径": list(knowledge.assets.report_texts),
            "图片文件路径": list(knowledge.assets.images),
            "视频文件路径": list(knowledge.assets.videos),
        },
        "evidence_policy": {
            "qa_allowed_confidence": ["confirmed"],
            "content_generation_can_use_review_pending": True,
            "compiled_artifact_do_not_edit_directly": True,
        },
    }
    competitor = {
        **common,
        "competitors": [],
        "inferred_items": [],
        "notes": "首版按产品保留竞品知识包边界；全库市场、竞品和潜在客户资料进入market知识域，raw层资料默认可信。",
    }
    content = {
        **common,
        "materials": {
            "selling_points": knowledge.facts.get("核心卖点", []),
            "scenarios": knowledge.facts.get("适用场景", []),
            "constraints": [
                "不存固定成稿",
                "对外草稿必须保留复核标记",
                "安全、认证、健康、环保claim需复核",
            ],
        },
    }
    video = {
        **common,
        "videos": [
            {
                "source_path": path,
                "duration_seconds": 0,
                "keyframes": [],
                "usable_for": ["product_intro", "application_scene"],
                "prompt_fragments": [],
                "review_notes": [f"视频视觉描述需由ffmpeg关键帧和{config.default_vision_model}补充。"],
            }
            for path in knowledge.assets.videos
        ],
    }
    evidence = {
        **common,
        "confirmed_sources": ["raw/00_知识库核心资料"],
        "review_required_claims": list(knowledge.inferred_claims),
        "conflicts": [],
        "policy": {
            "internal_qa_blocks_review_pending_claims": True,
            "content_generation_preserves_review_marks": True,
            "write_back_target": "raw/00_知识库核心资料/",
        },
    }

    write_json(packs_dir / "products" / f"{product}.json", facts)
    write_json(packs_dir / "competitors" / f"{product}.json", competitor)
    write_json(packs_dir / "content" / f"{product}.json", content)
    write_json(packs_dir / "video" / f"{product}.json", video)
    write_json(packs_dir / "evidence" / f"{product}.json", evidence)
    write_readable(packs_dir / "readable" / f"{product}.md", knowledge)


def remove_product_packs(packs_dir: Path, product: str) -> None:
    for dirname in PACK_DIRECTORIES.values():
        suffix = ".md" if dirname == "readable" else ".json"
        path = packs_dir / dirname / f"{product}{suffix}"
        if path.exists():
            path.unlink()


def write_readable(path: Path, knowledge: ProductKnowledge) -> None:
    facts = knowledge.facts
    lines = [
        f"# {knowledge.product.name}",
        "",
        f"- 状态：{knowledge.status}",
        f"- 素材状态：{knowledge.asset_status}",
        f"- 品牌：{facts.get('品牌', '')}",
        f"- 材料：{facts.get('材料', '')}",
        f"- 极限耐温：{facts.get('极限耐温', '')}",
        f"- 长期使用温度：{facts.get('长期使用温度', '')}",
        f"- 核心卖点：{'、'.join(facts.get('核心卖点', []))}",
        f"- 适用场景：{'、'.join(facts.get('适用场景', []))}",
        f"- 禁用场景：{'、'.join(facts.get('禁用场景', []))}",
        "",
        "## 素材",
        "",
        f"- 报告：{len(knowledge.assets.reports)}",
        f"- 图片：{len(knowledge.assets.images)}",
        f"- 视频：{len(knowledge.assets.videos)}",
    ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
