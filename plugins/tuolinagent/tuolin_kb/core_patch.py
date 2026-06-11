from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from .config import ProjectConfig, load_project_config
from .generate_agent_packs import generate_agent_packs
from .graphify_runner import build_graph
from .paths import resolve_project_path, resolve_raw_dir, source_path
from .review import collect_review_claims


CN_TZ = timezone(timedelta(hours=8))
CONFIRM_TOKEN = "WRITE_CORE_KNOWLEDGE"


@dataclass(frozen=True)
class CorePatchPreview:
    patch_path: Path
    preview_path: Path
    target_path: Path
    append_text: str


@dataclass(frozen=True)
class CorePatchApplyResult:
    target_path: Path
    graph_path: Path
    manifest_path: Path
    regeneration_succeeded: bool
    message: str


def create_core_patch_preview(
    root: Path | str = ".",
    *,
    claim_index: int,
    config: ProjectConfig | None = None,
) -> CorePatchPreview:
    root_path = Path(root).resolve()
    cfg = config or load_project_config(root_path)
    claims = collect_review_claims(root_path, cfg)
    if claim_index < 1 or claim_index > len(claims):
        raise ValueError(f"复核条目编号无效：{claim_index}。当前共有 {len(claims)} 条。")

    claim = claims[claim_index - 1]
    target_path = choose_core_target(root_path, cfg)
    append_text = build_append_text(claim)
    patch_dir = root_path / cfg.packs_dir / "review" / "core-patches"
    patch_dir.mkdir(parents=True, exist_ok=True)
    patch_id = patch_id_for_claim(claim)
    patch_path = patch_dir / f"{patch_id}.json"
    preview_path = patch_dir / f"{patch_id}.md"
    payload = {
        "schema_version": "1.0",
        "generated_by": "tuolinagent",
        "generated_at": datetime.now(CN_TZ).isoformat(timespec="seconds"),
        "status": "preview",
        "claim_index": claim_index,
        "claim": claim,
        "target_path": source_path(root_path, target_path),
        "append_text": append_text,
        "confirmation_required": CONFIRM_TOKEN,
        "policy": {
            "do_not_modify_graph_json_directly": True,
            "do_not_modify_agent_packs_directly": True,
            "regenerate_after_write": True,
        },
    }
    patch_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    preview_path.write_text(render_preview(payload), encoding="utf-8")
    return CorePatchPreview(
        patch_path=patch_path,
        preview_path=preview_path,
        target_path=target_path,
        append_text=append_text,
    )


def apply_core_patch(
    root: Path | str = ".",
    *,
    patch_path: Path | str,
    confirm_token: str,
    config: ProjectConfig | None = None,
) -> CorePatchApplyResult:
    root_path = Path(root).resolve()
    cfg = config or load_project_config(root_path)
    if confirm_token != CONFIRM_TOKEN:
        raise ValueError(f"缺少人工确认。确认写入必须传入：{CONFIRM_TOKEN}")

    patch = json.loads((root_path / patch_path).read_text(encoding="utf-8") if not Path(patch_path).is_absolute() else Path(patch_path).read_text(encoding="utf-8"))
    target_path = resolve_project_path(root_path, patch["target_path"])
    append_text = patch["append_text"]
    target_path.parent.mkdir(parents=True, exist_ok=True)
    current = target_path.read_text(encoding="utf-8", errors="ignore") if target_path.exists() else ""
    separator = "" if not current or current.endswith("\n") else "\n"
    target_path.write_text(current + separator + append_text, encoding="utf-8")

    try:
        graph_result = build_graph(root_path, update=True, config=cfg)
        pack_result = generate_agent_packs(root_path, config=cfg)
    except Exception as exc:  # pragma: no cover - exercised by integration failures
        return CorePatchApplyResult(
            target_path=target_path,
            graph_path=root_path / cfg.output_dir / "graph.json",
            manifest_path=root_path / cfg.packs_dir / "manifest.json",
            regeneration_succeeded=False,
            message=f"核心资料已写入，但再生成失败：{exc}",
        )

    mark_patch_applied(root_path, patch_path)
    return CorePatchApplyResult(
        target_path=target_path,
        graph_path=graph_result.graph_path,
        manifest_path=pack_result.manifest_path,
        regeneration_succeeded=True,
        message="核心资料已写入，并已重新生成数字资产层和Agent知识包。",
    )


def choose_core_target(root: Path, config: ProjectConfig) -> Path:
    core_dir = resolve_raw_dir(root, config) / "00_知识库核心资料"
    preferred = core_dir / "耐高温隔热带产品核心资料_完整版.md"
    if preferred.exists():
        return preferred
    candidates = sorted(path for path in core_dir.glob("*") if path.suffix.lower() in {".md", ".txt"})
    if candidates:
        return candidates[0]
    return core_dir / "人工复核补充.md"


def build_append_text(claim: dict[str, Any]) -> str:
    now = datetime.now(CN_TZ).strftime("%Y-%m-%d")
    product = claim.get("product", "全库资料")
    source = claim.get("source_path", "")
    text = claim.get("claim", "")
    return "\n".join(
        [
            "",
            "## 人工复核补充",
            "",
            f"### {now}｜{product}",
            "",
            f"- 已确认内容：{text}",
            f"- 来源：{source}",
            "- 复核状态：已确认",
            "",
        ]
    )


def render_preview(payload: dict[str, Any]) -> str:
    claim = payload["claim"]
    lines = [
        "# 核心资料修改预览",
        "",
        "该文件只是预览，不会自动修改核心资料。",
        "",
        f"- 目标文件：{payload['target_path']}",
        f"- 复核条目：{payload['claim_index']}",
        f"- 产品：{claim.get('product', '')}",
        f"- 来源：{claim.get('source_path', '')}",
        "",
        "## 准备追加的内容",
        "",
        "```markdown",
        payload["append_text"].strip(),
        "```",
        "",
        f"确认写入时必须使用确认令牌：`{CONFIRM_TOKEN}`",
        "",
    ]
    return "\n".join(lines)


def patch_id_for_claim(claim: dict[str, Any]) -> str:
    raw = "|".join([claim.get("product", ""), claim.get("source_path", ""), claim.get("claim", "")])
    import hashlib

    return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:16]


def mark_patch_applied(root: Path, patch_path: Path | str) -> None:
    path = root / patch_path if not Path(patch_path).is_absolute() else Path(patch_path)
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["status"] = "applied"
    payload["applied_at"] = datetime.now(CN_TZ).isoformat(timespec="seconds")
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
