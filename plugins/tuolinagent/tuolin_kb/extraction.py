from __future__ import annotations

import hashlib
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from .build_partitions import product_partition_name_for_target, refresh_manifest_build_partitions
from .config import ProjectConfig, load_project_config
from .local_graph import write_local_graph_outputs


CN_TZ = timezone(timedelta(hours=8))


def create_extraction_tasks(root: Path | str = ".", config: ProjectConfig | None = None) -> list[dict[str, Any]]:
    root_path = Path(root).resolve()
    cfg = config or load_project_config(root_path)
    packs_dir = root_path / cfg.packs_dir
    tasks: list[dict[str, Any]] = []

    for product_pack_path in sorted((packs_dir / "products").glob("*.json")):
        pack = json.loads(product_pack_path.read_text(encoding="utf-8"))
        product = pack["product"]
        facts = pack.get("facts", {})
        for source_path in facts.get("图片文件路径", []):
            tasks.append(
                build_task(
                    product=product,
                    source_path=source_path,
                    source_type="product_image",
                    target_pack=f"products/{product}.json",
                    prompt="识别产品图片中的产品、场景、可见特征。raw层资料默认准确；只有资料冲突、文件无法解析或你明确无法判断时，才标记需要人工确认。",
                )
            )
        for source_path in facts.get("检测报告正文路径", []):
            tasks.append(
                build_task(
                    product=product,
                    source_path=source_path,
                    source_type="product_report",
                    target_pack=f"products/{product}.json",
                    prompt=(
                        "读取检测报告Markdown正文，识别报告归属、页面摘要、检测信息和适用产品。raw层资料默认准确；"
                        "只有资料冲突、文件无法解析或你明确无法判断时，才标记需要人工确认。"
                    ),
                )
            )

    tasks.extend(create_domain_extraction_tasks(root_path, cfg, packs_dir))

    for video_pack_path in sorted((packs_dir / "video").glob("*.json")):
        pack = json.loads(video_pack_path.read_text(encoding="utf-8"))
        product = pack["product"]
        for video in pack.get("videos", []):
            keyframes = video.get("keyframes", [])
            if not keyframes:
                tasks.append(
                    build_task(
                        product=product,
                        source_path=video.get("source_path", ""),
                        source_type="product_video",
                        target_pack=f"video/{product}.json",
                        prompt="该视频尚未抽取关键帧。请先使用ffmpeg关键帧流程，再由Codex理解关键帧。",
                    )
                )
                continue
            for keyframe in keyframes:
                if keyframe.get("visual_description"):
                    continue
                tasks.append(
                    build_task(
                        product=product,
                        source_path=keyframe["frame_path"],
                        source_type="video_keyframe",
                        target_pack=f"video/{product}.json",
                        prompt="理解关键帧画面，输出visual_description、detected_product、detected_scene、confidence和review_required。raw层资料默认准确；只有资料冲突、文件无法解析或你明确无法判断时，才标记需要人工确认。",
                        metadata={
                            "video_source_path": video.get("source_path", ""),
                            "timestamp": keyframe.get("timestamp", ""),
                        },
                    )
                )

    return deduplicate_tasks(tasks)


def write_pending_extraction_tasks(
    root: Path | str,
    tasks: list[dict[str, Any]],
    config: ProjectConfig | None = None,
) -> Path:
    root_path = Path(root).resolve()
    cfg = config or load_project_config(root_path)
    task_path = root_path / cfg.packs_dir / "extraction" / "tasks.json"
    task_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema_version": "1.0",
        "generated_at": datetime.now(CN_TZ).isoformat(timespec="seconds"),
        "generated_by": "tuolinagent",
        "executor": "codex",
        "tasks": tasks,
    }
    task_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    refresh_manifest_build_partitions(root_path, cfg)
    return task_path


def apply_extraction_results(
    root: Path | str = ".",
    config: ProjectConfig | None = None,
    *,
    partition_name: str | None = None,
) -> int:
    root_path = Path(root).resolve()
    cfg = config or load_project_config(root_path)
    extraction_dir = root_path / cfg.packs_dir / "extraction"
    task_path = extraction_dir / "tasks.json"
    results_dir = extraction_dir / "results"
    if not task_path.exists() or not results_dir.exists():
        return 0

    tasks = {item["task_id"]: item for item in json.loads(task_path.read_text(encoding="utf-8")).get("tasks", [])}
    applied = 0
    for result_path in sorted(results_dir.glob("*.json")):
        result = json.loads(result_path.read_text(encoding="utf-8"))
        task = tasks.get(result.get("task_id"))
        if not task or result.get("status") != "completed" or result.get("applied") is True:
            continue
        result = normalize_automatic_result(task, result)
        result["partition_name"] = result.get("partition_name") or task.get("partition_name") or product_partition_name_for_target(
            task.get("target_pack", ""),
            task.get("product", ""),
        )
        if partition_name and result["partition_name"] != partition_name:
            continue
        if is_domain_task(task):
            update_domain_pack_result(root_path, cfg, task, result)
        else:
            if task["source_type"] == "video_keyframe":
                update_video_keyframe_result(root_path, cfg, task, result)
            append_review_claim(root_path, cfg, task, result)
        task["status"] = "applied"
        result["applied"] = True
        result_path.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        applied += 1

    task_payload = json.loads(task_path.read_text(encoding="utf-8"))
    task_payload["tasks"] = list(tasks.values())
    task_path.write_text(json.dumps(task_payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if applied:
        write_local_graph_outputs(root_path, cfg)
        refresh_manifest_build_partitions(root_path, cfg)
    return applied


def build_task(
    *,
    product: str,
    source_path: str,
    source_type: str,
    target_pack: str,
    prompt: str,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    task_key = f"{product}|{source_type}|{source_path}|{target_pack}"
    return {
        "task_id": hashlib.sha1(task_key.encode("utf-8")).hexdigest()[:16],
        "executor": "codex",
        "status": "pending",
        "partition_name": product_partition_name_for_target(target_pack, product),
        "product": product,
        "source_path": source_path,
        "source_type": source_type,
        "target_pack": target_pack,
        "prompt": prompt,
        "metadata": metadata or {},
        "result_schema": {
            "status": "completed",
            "partition_name": product_partition_name_for_target(target_pack, product),
            "applied": False,
            "visual_description": "string",
            "detected_product": "string",
            "detected_scene": "string",
            "confidence": "confirmed|inferred|uncertain",
            "review_required": "boolean",
        },
    }


def deduplicate_tasks(tasks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[str] = set()
    output: list[dict[str, Any]] = []
    for task in tasks:
        if task["task_id"] in seen:
            continue
        seen.add(task["task_id"])
        output.append(task)
    return output


def create_domain_extraction_tasks(root: Path, config: ProjectConfig, packs_dir: Path) -> list[dict[str, Any]]:
    tasks: list[dict[str, Any]] = []
    company_path = packs_dir / "company" / "company.json"
    if company_path.exists():
        pack = json.loads(company_path.read_text(encoding="utf-8"))
        for asset in pack.get("assets", []):
            source_path = asset.get("text_source_path") or asset.get("source_path", "")
            if asset.get("file_type") == "document" and not asset.get("text_source_path"):
                continue
            tasks.append(
                build_task(
                    product="公司",
                    source_path=source_path,
                    source_type=asset.get("source_type", "company_asset"),
                    target_pack="company/company.json",
                    prompt=(
                        "总结公司资料中的关键信息；如果来源是PDF转换出的Markdown，按Markdown正文整理。raw层资料默认准确；只有资料冲突、"
                        "文件无法解析或你明确无法判断时，才标记需要人工确认。"
                    ),
                    metadata={"original_source_path": asset.get("source_path", "")},
                )
            )

    standards_path = packs_dir / "standards" / "standards.json"
    if standards_path.exists():
        pack = json.loads(standards_path.read_text(encoding="utf-8"))
        for standard in pack.get("standards", []):
            source_path = standard.get("text_source_path") or standard.get("source_path", "")
            if standard.get("file_type") == "document" and not standard.get("text_source_path"):
                continue
            tasks.append(
                build_task(
                    product="标准",
                    source_path=source_path,
                    source_type=standard.get("source_type", "standard_asset"),
                    target_pack="standards/standards.json",
                    prompt=(
                        "总结标准文件名称、适用范围和与耐高温隔热带相关的信息；如果来源是PDF转换出的Markdown，按Markdown正文整理。raw层资料默认准确；"
                        "只有资料冲突、文件无法解析或你明确无法判断时，才标记需要人工确认。"
                    ),
                    metadata={"original_source_path": standard.get("source_path", "")},
                )
            )

    market_path = packs_dir / "market" / "market.json"
    if market_path.exists():
        pack = json.loads(market_path.read_text(encoding="utf-8"))
        for asset in pack.get("market_overview", []):
            if is_unreadable_document_asset(asset):
                continue
            tasks.append(build_market_task(asset, "市场现状", "market/market.json"))
        for competitor in pack.get("competitors", []):
            for asset in competitor.get("assets", []):
                if is_unreadable_document_asset(asset):
                    continue
                tasks.append(build_market_task(asset, f"竞争对手：{competitor.get('name', '')}", "market/market.json"))
        for prospect in pack.get("prospects", []):
            for asset in prospect.get("assets", []):
                if is_unreadable_document_asset(asset):
                    continue
                tasks.append(build_market_task(asset, f"潜在客户：{prospect.get('name', '')}", "market/market.json"))
    return tasks


def is_unreadable_document_asset(asset: dict[str, Any]) -> bool:
    return asset.get("file_type") == "document" and not asset.get("text_source_path") and asset.get("source_path", "").lower().endswith(".pdf")


def build_market_task(asset: dict[str, Any], topic: str, target_pack: str) -> dict[str, Any]:
    source_path = asset.get("text_source_path") or asset.get("source_path", "")
    return build_task(
        product=topic,
        source_path=source_path,
        source_type=asset.get("source_type", "market_asset"),
        target_pack=target_pack,
        prompt=(
            f"总结{topic}资料中的品牌、产品、卖点、场景和可用于后续业务Agent的信息；如果来源是PDF转换出的Markdown，按Markdown正文整理。"
            "raw层资料默认准确；只有资料冲突、文件无法解析或你明确无法判断时，才标记需要人工确认。"
        ),
        metadata={"original_source_path": asset.get("source_path", "")},
    )


def is_domain_task(task: dict[str, Any]) -> bool:
    return task.get("target_pack") in {"company/company.json", "standards/standards.json", "market/market.json"}


def normalize_automatic_result(task: dict[str, Any], result: dict[str, Any]) -> dict[str, Any]:
    normalized = dict(result)
    normalized.setdefault("applied", False)
    confidence = normalized.get("confidence", "confirmed")
    text = " ".join(
        str(normalized.get(key, ""))
        for key in ["visual_description", "claim", "detected_scene"]
    )
    has_blocking_signal = confidence == "uncertain" or any(
        token in text for token in ["无法", "不能可靠", "需人工复核", "需要人工复核", "冲突", "无法判断"]
    )
    normalized["confidence"] = "uncertain" if has_blocking_signal else "confirmed"
    normalized["review_required"] = has_blocking_signal
    return normalized


def update_video_keyframe_result(root: Path, config: ProjectConfig, task: dict[str, Any], result: dict[str, Any]) -> None:
    product = task["product"]
    pack_path = root / config.packs_dir / "video" / f"{product}.json"
    pack = json.loads(pack_path.read_text(encoding="utf-8"))
    for video in pack.get("videos", []):
        for keyframe in video.get("keyframes", []):
            if keyframe.get("frame_path") != task["source_path"]:
                continue
            keyframe["visual_description"] = result.get("visual_description", "")
            keyframe["detected_product"] = result.get("detected_product", "")
            keyframe["detected_scene"] = result.get("detected_scene", "")
            keyframe["confidence"] = result.get("confidence", "inferred")
            keyframe["review_required"] = bool(result.get("review_required", True))
    pack_path.write_text(json.dumps(pack, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def update_domain_pack_result(root: Path, config: ProjectConfig, task: dict[str, Any], result: dict[str, Any]) -> None:
    pack_path = root / config.packs_dir / task["target_pack"]
    pack = json.loads(pack_path.read_text(encoding="utf-8"))
    update_asset_collection(pack.get("assets", []), task, result)
    update_asset_collection(pack.get("standards", []), task, result)
    update_asset_collection(pack.get("market_overview", []), task, result)
    for competitor in pack.get("competitors", []):
        update_asset_collection(competitor.get("assets", []), task, result)
    for prospect in pack.get("prospects", []):
        update_asset_collection(prospect.get("assets", []), task, result)

    if result.get("review_required"):
        items = pack.setdefault("review_required_items", [])
        items = [item for item in items if item.get("task_id") != task["task_id"]]
        pack["review_required_items"] = items
        items.append(
            {
                "claim": result.get("visual_description") or result.get("claim") or "资料分析结果需要人工确认",
                "source_path": task["source_path"],
                "source_type": task["source_type"],
                "confidence": result.get("confidence", "uncertain"),
                "status": "pending",
                "task_id": task["task_id"],
            }
        )
    pack_path.write_text(json.dumps(pack, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def update_asset_collection(collection: list[dict[str, Any]], task: dict[str, Any], result: dict[str, Any]) -> None:
    for asset in collection:
        if asset.get("source_path") != task.get("source_path") and asset.get("source_path") != task.get("metadata", {}).get("original_source_path"):
            continue
        asset["summary"] = result.get("visual_description") or result.get("claim") or asset.get("summary", "")
        asset["detected_product"] = result.get("detected_product", "")
        asset["detected_scene"] = result.get("detected_scene", "")
        asset["confidence"] = result.get("confidence", "confirmed")
        asset["review_required"] = bool(result.get("review_required", False))


def append_review_claim(root: Path, config: ProjectConfig, task: dict[str, Any], result: dict[str, Any]) -> None:
    product = task["product"]
    evidence_path = root / config.packs_dir / "evidence" / f"{product}.json"
    evidence = json.loads(evidence_path.read_text(encoding="utf-8"))
    claims = evidence.setdefault("review_required_claims", [])
    confidence = result.get("confidence", "inferred")
    review_required = bool(result.get("review_required", True))
    if not review_required:
        return
    claim = result.get("visual_description") or result.get("claim") or f"{task['source_type']} 抽取结果待复核"
    claims = [item for item in claims if item.get("task_id") != task["task_id"]]
    evidence["review_required_claims"] = claims
    claims.append(
        {
            "claim": claim,
            "product": product,
            "source_path": task["source_path"],
            "source_type": task["source_type"],
            "confidence": confidence,
            "status": "pending",
            "task_id": task["task_id"],
        }
    )
    evidence_path.write_text(json.dumps(evidence, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
