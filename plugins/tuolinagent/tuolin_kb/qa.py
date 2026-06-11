from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from .config import ProjectConfig, load_project_config


@dataclass(frozen=True)
class QAResult:
    answered: bool
    answer: str
    sources: tuple[str, ...] = ()


def answer_question(root: Path | str, question: str, config: ProjectConfig | None = None) -> QAResult:
    root_path = Path(root).resolve()
    cfg = config or load_project_config(root_path)
    manifest_path = root_path / cfg.packs_dir / "manifest.json"
    if not manifest_path.exists():
        return QAResult(False, "无法给出已确认答案：尚未生成Agent知识包。")

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    product = detect_product(question, [item["name"] for item in manifest.get("products", [])])
    if not product:
        return QAResult(False, "无法给出已确认答案：没有定位到四个核心产品。")

    product_pack_path = root_path / cfg.packs_dir / "products" / f"{product}.json"
    product_pack = json.loads(product_pack_path.read_text(encoding="utf-8"))
    if product_pack.get("confidence") != "confirmed":
        return QAResult(False, "无法给出已确认答案：对应知识包不是confirmed。")

    facts = product_pack.get("facts", {})
    if "视频" in question or "画面" in question:
        return answer_video_question(root_path, cfg, product)

    if "适合" in question or "推荐" in question or "能用" in question:
        scenarios = facts.get("适用场景", [])
        matched = [scenario for scenario in scenarios if scenario and scenario in question]
        if matched:
            return QAResult(
                True,
                f"可以。{product}的已确认适用场景包含：{'、'.join(matched)}。",
                (str(product_pack_path),),
            )
        if scenarios:
            return QAResult(
                True,
                f"{product}的已确认适用场景包括：{'、'.join(scenarios)}。",
                (str(product_pack_path),),
            )

    selling_points = facts.get("核心卖点", [])
    if "卖点" in question and selling_points:
        return QAResult(True, f"{product}的已确认核心卖点包括：{'、'.join(selling_points)}。", (str(product_pack_path),))

    return QAResult(False, "无法给出已确认答案：Agent知识包没有覆盖这个问题。")


def detect_product(question: str, products: list[str]) -> str | None:
    for product in products:
        if product in question:
            return product
    for product in products:
        short = product.replace("纤维隔热带", "").replace("隔热带", "")
        if short and short in question:
            return product
    return None


def answer_video_question(root: Path, config: ProjectConfig, product: str) -> QAResult:
    video_pack_path = root / config.packs_dir / "video" / f"{product}.json"
    if not video_pack_path.exists():
        return QAResult(False, "无法给出已确认答案：没有找到该产品的视频素材信息。")
    pack = json.loads(video_pack_path.read_text(encoding="utf-8"))
    descriptions: list[str] = []
    pending = 0
    for video in pack.get("videos", []):
        for keyframe in video.get("keyframes", []):
            description = keyframe.get("visual_description", "")
            if not description:
                continue
            if keyframe.get("review_required"):
                pending += 1
                continue
            descriptions.append(description)
    if descriptions:
        return QAResult(
            True,
            f"{product}的已确认视频画面包括：{'；'.join(descriptions[:3])}。",
            (str(video_pack_path),),
        )
    if pending:
        return QAResult(False, "无法给出已确认答案：相关视频画面仍需要人工确认。")
    return QAResult(False, "无法给出已确认答案：Agent知识包没有已确认的视频画面描述。")
