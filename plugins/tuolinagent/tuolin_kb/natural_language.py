from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from .config import ProjectConfig, load_project_config
from .products import collect_product_knowledge
from .status import StatusReport, load_status


ActionKind = Literal["build_partition", "organize_usable", "continue_review", "use_existing", "update_first", "prepare_raw"]


@dataclass(frozen=True)
class OrganizeRecommendation:
    action: ActionKind
    partition_name: str | None
    reason: str
    result_summary: str
    needs_confirmation: bool


PRODUCT_PRIORITY = {
    "石英纤维隔热带": 0,
    "陶瓷纤维隔热带": 1,
    "玄武岩纤维隔热带": 2,
    "高硅氧纤维隔热带": 3,
    "公司": 4,
    "标准": 5,
    "市场": 6,
}


def recommend_organize_next_step(
    root: Path | str = ".",
    config: ProjectConfig | None = None,
) -> OrganizeRecommendation:
    root_path = Path(root).resolve()
    cfg = config or load_project_config(root_path)
    if not (root_path / cfg.packs_dir / "manifest.json").exists():
        return recommend_initial_build(root_path, cfg)
    report = load_status(root_path, cfg)
    partitions = report.build_partitions

    needs_update = [item for item in partitions if item.get("status") == "needs_update"]
    if needs_update:
        target = sorted(needs_update, key=partition_priority)[0]
        return OrganizeRecommendation(
            action="update_first",
            partition_name=target["name"],
            reason=f"{target['name']}的资料已经变化，需要先更新这个分区。",
            result_summary="更新后，我再继续判断哪些资料可以整理成可用内容。",
            needs_confirmation=True,
        )

    pending_results = [item for item in partitions if item.get("pending_result_count", 0) > 0]
    if pending_results:
        target = sorted(pending_results, key=partition_priority)[0]
        return OrganizeRecommendation(
            action="organize_usable",
            partition_name=target["name"],
            reason=reason_for_partition(target),
            result_summary=(
                f"一批可以用于回答客户问题、写产品介绍和整理销售话术的{target['name']}信息；"
                "需要你判断的内容会单独列出来，不会混进确定答案。"
            ),
            needs_confirmation=True,
        )

    pending_materials = [item for item in partitions if item.get("pending_extraction_count", 0) > 0]
    if pending_materials:
        target = sorted(pending_materials, key=partition_priority)[0]
        return OrganizeRecommendation(
            action="continue_review",
            partition_name=target["name"],
            reason=f"{target['name']}还有资料没看完，继续处理后才能提炼出更多可用信息。",
            result_summary="我会继续查看图片、报告或视频画面，把有用信息整理出来，后续再变成可用资料。",
            needs_confirmation=True,
        )

    ready = [item for item in partitions if item.get("status") == "ready"]
    if ready:
        target = sorted(ready, key=partition_priority)[0]
        return OrganizeRecommendation(
            action="use_existing",
            partition_name=target["name"],
            reason=f"{target['name']}当前资料已经可以使用，暂时没有新的内容需要整理。",
            result_summary="你现在可以直接让我回答客户常见问题、写产品介绍或整理销售话术。",
            needs_confirmation=False,
        )

    return OrganizeRecommendation(
        action="prepare_raw",
        partition_name=None,
        reason="当前还没有可整理的产品资料。",
        result_summary="请先按raw目录补齐产品图片、报告或视频，然后我再继续整理。",
        needs_confirmation=False,
    )


def format_organize_recommendation(recommendation: OrganizeRecommendation, report: StatusReport | None = None) -> str:
    if recommendation.action == "build_partition":
        return "\n".join(
            [
                f"我建议先整理{recommendation.partition_name}资料。",
                "",
                recommendation.reason,
                "",
                "整理后，你会得到：",
                f"- {recommendation.result_summary}",
                "",
                "这一步不会修改核心资料，也不会对外发布内容。",
                "",
                "请确认是否开始整理。",
            ]
        )

    if recommendation.action == "organize_usable":
        lines = [
            "我看了当前资料状态。",
            f"{recommendation.partition_name}最适合先整理，{recommendation.reason}",
            "",
            summarize_other_partitions(report, recommendation.partition_name),
            "",
            f"我建议下一步：先把{recommendation.partition_name}整理成可用资料。",
            "",
            "整理后，你会得到：",
            f"- {recommendation.result_summary}",
            "",
            "这一步不会修改核心资料，也不会对外发布内容。",
            "",
            "请确认是否开始整理。",
        ]
        return "\n".join(lines)

    if recommendation.action == "continue_review":
        return "\n".join(
            [
                f"我建议继续看{recommendation.partition_name}剩下的资料。",
                "",
                recommendation.result_summary,
                "",
                "这一步不会修改核心资料，也不会对外发布内容。",
                "",
                "请确认是否继续。",
            ]
        )

    if recommendation.action == "update_first":
        return "\n".join(
            [
                recommendation.reason,
                recommendation.result_summary,
                "",
                "请确认是否先更新这个分区。",
            ]
        )

    if recommendation.action == "use_existing":
        return "\n".join(
            [
                recommendation.reason,
                "",
                recommendation.result_summary,
                "",
                "如果你新增了图片、报告或视频，我再继续整理。",
            ]
        )

    return "\n".join([recommendation.reason, recommendation.result_summary])


def load_organize_recommendation_text(root: Path | str = ".", config: ProjectConfig | None = None) -> str:
    root_path = Path(root).resolve()
    cfg = config or load_project_config(root_path)
    if not (root_path / cfg.packs_dir / "manifest.json").exists():
        recommendation = recommend_initial_build(root_path, cfg)
        return format_organize_recommendation(recommendation)
    report = load_status(root_path, cfg)
    recommendation = recommend_organize_next_step(root_path, cfg)
    return format_organize_recommendation(recommendation, report)


def recommend_initial_build(root: Path, config: ProjectConfig) -> OrganizeRecommendation:
    products = collect_product_knowledge(root, config)
    ready_products = [item for item in products if item.status == "ready"]
    if ready_products:
        target = sorted(ready_products, key=lambda item: PRODUCT_PRIORITY.get(item.product.name, 99))[0]
        return OrganizeRecommendation(
            action="build_partition",
            partition_name=target.product.name,
            reason="这个产品的图片、报告和视频资料已经比较完整，整理后最快能用于回答客户问题、写产品介绍和整理销售话术。",
            result_summary=f"{target.product.name}的基础产品信息、素材路径和后续待看资料清单。",
            needs_confirmation=True,
        )

    partial_products = [item for item in products if item.status == "incomplete_assets"]
    if partial_products:
        target = sorted(partial_products, key=lambda item: PRODUCT_PRIORITY.get(item.product.name, 99))[0]
        return OrganizeRecommendation(
            action="build_partition",
            partition_name=target.product.name,
            reason="这个产品已经有部分资料，可以先整理出基础信息，同时标出还缺哪些素材。",
            result_summary=f"{target.product.name}当前已有资料的基础整理，以及需要补充的素材清单。",
            needs_confirmation=True,
        )

    return OrganizeRecommendation(
        action="prepare_raw",
        partition_name=None,
        reason="当前还没有可整理的产品资料。",
        result_summary="请先按raw目录补齐产品图片、报告或视频，然后我再继续整理。",
        needs_confirmation=False,
    )


def partition_priority(item: dict) -> tuple[int, int, str]:
    type_priority = 0 if item.get("type") == "product" and item.get("status") == "ready" else 1
    return (type_priority, PRODUCT_PRIORITY.get(item.get("name", ""), 99), item.get("name", ""))


def reason_for_partition(item: dict) -> str:
    if item.get("type") == "product" and item.get("status") == "ready":
        return "因为它已有基础资料，整理后最快能用于回答客户问题、写产品介绍和整理销售话术。"
    return "因为它已经有识别出的内容，整理后可以先补充到可用资料里。"


def summarize_other_partitions(report: StatusReport | None, selected_name: str | None) -> str:
    if report is None:
        return ""
    available = [
        item["name"]
        for item in report.build_partitions
        if item.get("name") != selected_name
        and item.get("status") != "not_built"
        and (item.get("pending_extraction_count", 0) > 0 or item.get("pending_result_count", 0) > 0)
    ]
    missing = [
        item["name"]
        for item in report.build_partitions
        if item.get("type") == "product" and item.get("status") == "not_built"
    ]
    parts = []
    if available:
        parts.append(f"{'、'.join(available)}也有资料可继续整理")
    if missing:
        parts.append(f"{'、'.join(missing)}还需要先补齐产品素材")
    return "；".join(parts) + "。" if parts else ""
