from __future__ import annotations

import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

from .config import ProjectConfig
from .paths import cache_key_for_path, resolve_project_path, resolve_raw_dir


PDF_SUFFIX = ".pdf"


@dataclass(frozen=True)
class DocumentConversionResult:
    pdf_path: Path
    markdown_path: Path
    status: str
    message: str


def markdown_path_for_pdf(pdf_path: Path) -> Path:
    return pdf_path.with_suffix(".md")


def relative_path(root: Path, path: Path) -> str:
    return path.relative_to(root).as_posix()


def ensure_pdf_markdown_sources(
    root: Path | str,
    config: ProjectConfig,
    *,
    raw_paths: list[str] | tuple[str, ...] | None = None,
) -> list[DocumentConversionResult]:
    root_path = Path(root).resolve()
    scan_roots = [resolve_project_path(root_path, path) for path in raw_paths] if raw_paths is not None else [resolve_raw_dir(root_path, config)]
    results: list[DocumentConversionResult] = []
    for scan_root in scan_roots:
        if not scan_root.exists():
            continue
        for pdf_path in sorted(scan_root.rglob("*")):
            if not pdf_path.is_file() or pdf_path.suffix.lower() != PDF_SUFFIX or "graphify-out" in pdf_path.parts:
                continue
            results.append(ensure_pdf_markdown_source(root_path, config, pdf_path))
    return results


def ensure_pdf_markdown_source(root: Path, config: ProjectConfig, pdf_path: Path) -> DocumentConversionResult:
    markdown_path = markdown_path_for_pdf(pdf_path)
    if markdown_path.exists():
        return DocumentConversionResult(
            pdf_path=pdf_path,
            markdown_path=markdown_path,
            status="ready",
            message="同名Markdown已存在。",
        )
    if not config.mineru_enabled:
        return DocumentConversionResult(
            pdf_path=pdf_path,
            markdown_path=markdown_path,
            status="disabled",
            message="MinerU未启用，PDF正文未转换。",
        )
    executable = resolve_command(config.mineru_command)
    if executable is None:
        return DocumentConversionResult(
            pdf_path=pdf_path,
            markdown_path=markdown_path,
            status="missing_mineru",
            message="本机缺少MinerU，无法把PDF转换成Markdown。",
        )

    cache_dir = root / config.mineru_cache_dir / cache_key_for_path(root, pdf_path.with_suffix(""))
    cache_dir.mkdir(parents=True, exist_ok=True)
    command = [
        executable,
        "-p",
        str(pdf_path),
        "-o",
        str(cache_dir),
        "-b",
        config.mineru_backend,
        "-l",
        config.mineru_lang,
    ]
    completed = subprocess.run(command, cwd=root, check=False, capture_output=True, text=True)
    if completed.returncode != 0:
        return DocumentConversionResult(
            pdf_path=pdf_path,
            markdown_path=markdown_path,
            status="failed",
            message=f"MinerU转换失败：{completed.stderr.strip() or completed.stdout.strip()}",
        )

    generated = find_generated_markdown(cache_dir, pdf_path.stem)
    if generated is None:
        return DocumentConversionResult(
            pdf_path=pdf_path,
            markdown_path=markdown_path,
            status="failed",
            message="MinerU转换完成，但未找到Markdown输出。",
        )
    shutil.copyfile(generated, markdown_path)
    return DocumentConversionResult(
        pdf_path=pdf_path,
        markdown_path=markdown_path,
        status="converted",
        message="已用MinerU转换为同名Markdown。",
    )


def resolve_command(command: str) -> str | None:
    path = Path(command)
    if path.parent != Path("."):
        return str(path) if path.exists() and path.is_file() else None
    return shutil.which(command)


def find_generated_markdown(cache_dir: Path, stem: str) -> Path | None:
    markdown_files = sorted(cache_dir.rglob("*.md"))
    if not markdown_files:
        return None
    exact = [path for path in markdown_files if path.stem == stem]
    if exact:
        return exact[0]
    return markdown_files[0]


def document_summary_for_missing_markdown(title: str) -> str:
    return f"{title} PDF还没有可读取正文；需要先用MinerU转换成同名Markdown后再整理具体内容。"
