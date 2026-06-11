from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .config import ProjectConfig, load_project_config


def collect_review_claims(root: Path | str = ".", config: ProjectConfig | None = None) -> list[dict[str, Any]]:
    root_path = Path(root).resolve()
    cfg = config or load_project_config(root_path)
    evidence_dir = root_path / cfg.packs_dir / "evidence"
    claims: list[dict[str, Any]] = []
    for path in sorted(evidence_dir.glob("*.json")):
        payload = json.loads(path.read_text(encoding="utf-8"))
        product = payload.get("product", path.stem)
        for item in payload.get("review_required_claims", []):
            if isinstance(item, str):
                claims.append(
                    {
                        "product": product,
                        "claim": item,
                        "confidence": "inferred",
                        "status": "pending",
                        "source_path": "",
                    }
                )
            else:
                normalized = dict(item)
                normalized.setdefault("product", product)
                normalized.setdefault("confidence", "inferred")
                normalized.setdefault("status", "pending")
                normalized.setdefault("source_path", "")
                claims.append(normalized)
    return claims


def format_review_claims(claims: list[dict[str, Any]]) -> str:
    if not claims:
        return "当前没有需要人工复核的内容。"
    lines = ["需要人工复核的内容：", ""]
    for index, claim in enumerate(claims, 1):
        lines.append(
            f"{index}. {claim.get('product', '')}｜{confidence_label(claim.get('confidence', ''))}｜"
            f"{claim.get('claim', '')}｜来源：{claim.get('source_path', '')}"
        )
    return "\n".join(lines)


def confidence_label(value: str) -> str:
    labels = {
        "confirmed": "已确认",
        "inferred": "待确认",
        "uncertain": "不确定",
        "pending": "待处理",
    }
    return labels.get(value, value or "待确认")
