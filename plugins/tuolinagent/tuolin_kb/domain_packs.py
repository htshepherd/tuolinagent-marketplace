from __future__ import annotations

import json
import re
import zipfile
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from xml.etree import ElementTree

from .config import ProjectConfig, load_project_config
from .constants import IMAGE_SUFFIXES, REPORT_SUFFIXES, VIDEO_SUFFIXES
from .document_conversion import document_summary_for_missing_markdown, markdown_path_for_pdf
from .paths import resolve_raw_dir, source_path


CN_TZ = timezone(timedelta(hours=8))


@dataclass(frozen=True)
class DomainPackOutput:
    company_path: Path
    standards_path: Path
    market_path: Path


def generate_domain_packs(root: Path | str = ".", config: ProjectConfig | None = None) -> DomainPackOutput:
    root_path = Path(root).resolve()
    cfg = config or load_project_config(root_path)
    packs_dir = root_path / cfg.packs_dir
    company_dir = packs_dir / "company"
    standards_dir = packs_dir / "standards"
    market_dir = packs_dir / "market"
    for directory in [company_dir, standards_dir, market_dir]:
        directory.mkdir(parents=True, exist_ok=True)

    company_path = company_dir / "company.json"
    standards_path = standards_dir / "standards.json"
    market_path = market_dir / "market.json"
    write_json(company_path, build_company_pack(root_path, cfg))
    write_json(standards_path, build_standards_pack(root_path, cfg))
    write_json(market_path, build_market_pack(root_path, cfg))
    return DomainPackOutput(company_path=company_path, standards_path=standards_path, market_path=market_path)


def build_company_pack(root: Path, config: ProjectConfig) -> dict[str, Any]:
    base = resolve_raw_dir(root, config) / "01_公司介绍"
    assets = []
    for path in iter_files(base):
        category = company_category(path)
        assets.append(build_asset(root, path, "company_asset", category))
    return {
        **common_pack("company"),
        "title": "公司介绍",
        "domain_label": "公司",
        "trust_policy": raw_trust_policy(),
        "assets": assets,
        "sections": group_by_category(assets),
        "review_required_items": [],
    }


def build_standards_pack(root: Path, config: ProjectConfig) -> dict[str, Any]:
    base = resolve_raw_dir(root, config) / "02_标准"
    standards = []
    for path in iter_files(base):
        standard = build_asset(root, path, "standard_asset", standard_category(path))
        standard["standard_name"] = path.stem
        standards.append(standard)
    return {
        **common_pack("standards"),
        "title": "标准资料",
        "domain_label": "标准",
        "trust_policy": raw_trust_policy(),
        "standards": standards,
        "review_required_items": [],
    }


def build_market_pack(root: Path, config: ProjectConfig) -> dict[str, Any]:
    base = resolve_raw_dir(root, config) / "03_市场"
    overview = []
    competitors: dict[str, list[dict[str, Any]]] = {}
    prospects: dict[str, list[dict[str, Any]]] = {}
    other = []
    for path in iter_files(base):
        relative = source_path(root, path)
        asset = build_asset(root, path, "market_asset", market_category(path))
        if "/01_市场现状/" in relative:
            overview.append(asset)
        elif "/02_竞争对手/" in relative:
            competitors.setdefault(parent_topic(path, "02_竞争对手"), []).append(asset)
        elif "/03_潜在客户/" in relative:
            prospects.setdefault(parent_topic(path, "03_潜在客户"), []).append(asset)
        else:
            other.append(asset)
    return {
        **common_pack("market"),
        "title": "市场资料",
        "domain_label": "市场",
        "trust_policy": raw_trust_policy(),
        "market_overview": overview,
        "competitors": [{"name": name, "assets": assets} for name, assets in sorted(competitors.items())],
        "prospects": [{"name": name, "assets": assets} for name, assets in sorted(prospects.items())],
        "other_assets": other,
        "review_required_items": [],
    }


def common_pack(domain: str) -> dict[str, Any]:
    return {
        "schema_version": "1.0",
        "generated_by": "tuolinagent",
        "generated_at": datetime.now(CN_TZ).isoformat(timespec="seconds"),
        "domain": domain,
        "confidence": "confirmed",
    }


def raw_trust_policy() -> dict[str, Any]:
    return {
        "raw_materials_default_confidence": "confirmed",
        "review_required_when": ["资料冲突", "文件无法解析", "Codex明确无法判断", "用户明确要求复核"],
    }


def iter_files(base: Path) -> list[Path]:
    if not base.exists():
        return []
    return [
        path
        for path in sorted(base.rglob("*"))
        if path.is_file()
        and path.name != ".DS_Store"
        and "graphify-out" not in path.parts
        and not (path.suffix.lower() == ".md" and path.with_suffix(".pdf").exists())
    ]


def build_asset(root: Path, path: Path, source_type: str, category: str) -> dict[str, Any]:
    relative = source_path(root, path)
    asset = {
        "title": readable_title(path),
        "source_path": relative,
        "source_type": source_type,
        "category": category,
        "file_type": file_type(path),
        "confidence": "confirmed",
        "review_required": False,
        "summary": summarize_file(path),
    }
    if path.suffix.lower() == ".pdf":
        markdown_path = markdown_path_for_pdf(path)
        if markdown_path.exists():
            asset["text_source_path"] = source_path(root, markdown_path)
            asset["text_source_type"] = "mineru_markdown"
            asset["document_conversion"] = {"status": "ready"}
        else:
            asset["confidence"] = "uncertain"
            asset["review_required"] = True
            asset["document_conversion"] = {
                "status": "missing_markdown",
                "message": "这份PDF还没有同名Markdown正文。",
            }
    return asset


def file_type(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix in IMAGE_SUFFIXES:
        return "image"
    if suffix in VIDEO_SUFFIXES:
        return "video"
    if suffix in REPORT_SUFFIXES:
        return "document"
    if suffix in {".md", ".txt"}:
        return "text"
    return suffix.lstrip(".") or "file"


def summarize_file(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix in {".md", ".txt"}:
        return summarize_text(path.read_text(encoding="utf-8", errors="ignore"))
    if suffix == ".pdf":
        markdown_path = markdown_path_for_pdf(path)
        if markdown_path.exists():
            return summarize_text(markdown_path.read_text(encoding="utf-8", errors="ignore"))
        return document_summary_for_missing_markdown(readable_title(path))
    if suffix == ".docx":
        text = read_docx_text(path)
        if text:
            return summarize_text(text)
    if suffix in IMAGE_SUFFIXES:
        return f"{readable_title(path)} 图片素材。"
    if suffix in VIDEO_SUFFIXES:
        return f"{readable_title(path)} 视频素材。"
    return f"{readable_title(path)} 文档资料。"


def read_docx_text(path: Path) -> str:
    try:
        with zipfile.ZipFile(path) as archive:
            xml = archive.read("word/document.xml")
    except (KeyError, OSError, zipfile.BadZipFile):
        return ""
    root = ElementTree.fromstring(xml)
    namespace = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
    parts = [node.text for node in root.iter(f"{namespace}t") if node.text]
    return "\n".join(parts)


def summarize_text(text: str, limit: int = 180) -> str:
    cleaned = " ".join(text.split())
    return cleaned if len(cleaned) <= limit else cleaned[: limit - 1] + "..."


def readable_title(path: Path) -> str:
    return re.sub(r"[_\\-]+", " ", path.stem).strip()


def company_category(path: Path) -> str:
    text = path.as_posix()
    if "01_公司介绍" in text:
        return "公司介绍"
    if "02_生产车间" in text:
        return "生产车间"
    if "03_企业资质" in text:
        return "企业资质"
    if "04_实验室校验检测" in text:
        return "实验室校验检测"
    return "公司资料"


def standard_category(path: Path) -> str:
    text = path.as_posix()
    if "01_国标" in text:
        return "国标"
    if "02_国际标准" in text:
        return "国际标准"
    return "标准资料"


def market_category(path: Path) -> str:
    text = path.as_posix()
    if "01_市场现状" in text:
        return "市场现状"
    if "02_竞争对手" in text:
        return "竞争对手"
    if "03_潜在客户" in text:
        return "潜在客户"
    return "市场资料"


def parent_topic(path: Path, marker: str) -> str:
    parts = path.parts
    if marker not in parts:
        return "未分类"
    index = parts.index(marker)
    return parts[index + 1] if index + 1 < len(parts) else "未分类"


def group_by_category(assets: list[dict[str, Any]]) -> list[dict[str, Any]]:
    groups: dict[str, list[dict[str, Any]]] = {}
    for asset in assets:
        groups.setdefault(asset["category"], []).append(asset)
    return [{"name": name, "assets": items} for name, items in sorted(groups.items())]


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
