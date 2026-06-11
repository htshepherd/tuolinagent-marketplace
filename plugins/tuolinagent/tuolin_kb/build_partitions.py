from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .config import ProjectConfig
from .constants import CORE_PRODUCTS, STATUS_LABELS
from .paths import resolve_project_path, resolve_raw_dir, source_path


@dataclass(frozen=True)
class BuildPartition:
    name: str
    type: str
    raw_path: str
    product_status: str | None = None


DOMAIN_PARTITIONS: tuple[BuildPartition, ...] = (
    BuildPartition(name="公司", type="domain", raw_path="raw/01_公司介绍"),
    BuildPartition(name="标准", type="domain", raw_path="raw/02_标准"),
    BuildPartition(name="市场", type="domain", raw_path="raw/03_市场"),
)


def product_partition_name_for_target(target_pack: str, product: str) -> str:
    if target_pack == "company/company.json":
        return "公司"
    if target_pack == "standards/standards.json":
        return "标准"
    if target_pack == "market/market.json":
        return "市场"
    return product


def build_partitions_manifest(
    root: Path,
    config: ProjectConfig,
    products: list[Any],
    *,
    update_fingerprints: bool = True,
) -> list[dict[str, Any]]:
    counts = partition_counts(root, config)
    partitions: list[BuildPartition] = []
    for knowledge in products:
        raw_path = knowledge.assets.product_dir or expected_product_raw_path(config, knowledge.product.name)
        partitions.append(
            BuildPartition(
                name=knowledge.product.name,
                type="product",
                raw_path=raw_path,
                product_status=knowledge.status,
            )
        )
    partitions.extend(
        BuildPartition(
            name=item.name,
            type=item.type,
            raw_path=domain_raw_path(config, item.raw_path),
        )
        for item in DOMAIN_PARTITIONS
    )

    output = []
    for partition in partitions:
        fingerprint = compute_partition_fingerprint(root, config, partition)
        fingerprint_changed = fingerprint_has_changed(root, config, partition, fingerprint)
        if update_fingerprints and partition.product_status != "not_built":
            write_partition_fingerprint(root, config, partition, fingerprint)
            fingerprint_changed = False
        status = partition_status(partition, counts, fingerprint_changed)
        output.append(
            {
                "name": partition.name,
                "type": partition.type,
                "status": status,
                "status_label": STATUS_LABELS.get(status, status),
                "raw_path": partition.raw_path,
                "last_built_at": None,
                "pending_extraction_count": counts.get(partition.name, {}).get("pending_extraction_count", 0),
                "pending_result_count": counts.get(partition.name, {}).get("pending_result_count", 0),
                "review_claim_count": counts.get(partition.name, {}).get("review_claim_count", 0),
            }
        )
    return output


def refresh_manifest_build_partitions(root: Path, config: ProjectConfig) -> None:
    manifest_path = root / config.packs_dir / "manifest.json"
    if not manifest_path.exists():
        return
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    products_by_name = {item.get("name"): item for item in manifest.get("products", [])}
    counts = partition_counts(root, config)
    output = []
    for item in manifest.get("build_partitions", []):
        name = item.get("name", "")
        partition = BuildPartition(
            name=name,
            type=item.get("type", ""),
            raw_path=item.get("raw_path", ""),
            product_status=products_by_name.get(name, {}).get("status"),
        )
        fingerprint = compute_partition_fingerprint(root, config, partition)
        status = partition_status(
            partition,
            counts,
            fingerprint_has_changed(root, config, partition, fingerprint),
        )
        updated = dict(item)
        updated.update(
            {
                "status": status,
                "status_label": STATUS_LABELS.get(status, status),
                "pending_extraction_count": counts.get(name, {}).get("pending_extraction_count", 0),
                "pending_result_count": counts.get(name, {}).get("pending_result_count", 0),
                "review_claim_count": counts.get(name, {}).get("review_claim_count", 0),
            }
        )
        output.append(updated)
    manifest["build_partitions"] = output
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def expected_product_raw_path(config: ProjectConfig, product_name: str) -> str:
    return f"{config.raw_dir}/04_产品/{product_name}"


def domain_raw_path(config: ProjectConfig, template_path: str) -> str:
    suffix = template_path.removeprefix("raw/")
    return f"{config.raw_dir.rstrip('/')}/{suffix}"


def partition_status(
    partition: BuildPartition,
    counts: dict[str, dict[str, int]],
    fingerprint_changed: bool,
) -> str:
    if partition.product_status == "not_built":
        return "not_built"
    if fingerprint_changed:
        return "needs_update"
    item_counts = counts.get(partition.name, {})
    if item_counts.get("pending_extraction_count", 0) > 0:
        return "pending_extraction"
    if (
        item_counts.get("pending_result_count", 0) > 0
        or item_counts.get("review_claim_count", 0) > 0
        or partition.product_status == "incomplete_assets"
    ):
        return "review_required"
    return "ready"


def partition_counts(root: Path, config: ProjectConfig) -> dict[str, dict[str, int]]:
    counts: dict[str, dict[str, int]] = {}

    task_path = root / config.packs_dir / "extraction" / "tasks.json"
    if task_path.exists():
        tasks = json.loads(task_path.read_text(encoding="utf-8")).get("tasks", [])
        for task in tasks:
            if task.get("status") != "pending":
                continue
            name = task.get("partition_name") or product_partition_name_for_target(
                task.get("target_pack", ""),
                task.get("product", ""),
            )
            counts.setdefault(name, {}).setdefault("pending_extraction_count", 0)
            counts[name]["pending_extraction_count"] += 1

    results_dir = root / config.packs_dir / "extraction" / "results"
    if results_dir.exists():
        for result_path in sorted(results_dir.glob("*.json")):
            result = json.loads(result_path.read_text(encoding="utf-8"))
            if result.get("status") != "completed" or result.get("applied") is True:
                continue
            name = result.get("partition_name") or partition_name_for_result(root, config, result)
            if not name:
                continue
            counts.setdefault(name, {}).setdefault("pending_result_count", 0)
            counts[name]["pending_result_count"] += 1

    add_review_counts(root, config, counts)
    return counts


def partition_name_for_result(root: Path, config: ProjectConfig, result: dict[str, Any]) -> str:
    task_id = result.get("task_id")
    task_path = root / config.packs_dir / "extraction" / "tasks.json"
    if not task_id or not task_path.exists():
        return ""
    for task in json.loads(task_path.read_text(encoding="utf-8")).get("tasks", []):
        if task.get("task_id") == task_id:
            return task.get("partition_name") or product_partition_name_for_target(
                task.get("target_pack", ""),
                task.get("product", ""),
            )
    return ""


def add_review_counts(root: Path, config: ProjectConfig, counts: dict[str, dict[str, int]]) -> None:
    evidence_dir = root / config.packs_dir / "evidence"
    if evidence_dir.exists():
        for path in sorted(evidence_dir.glob("*.json")):
            payload = json.loads(path.read_text(encoding="utf-8"))
            name = payload.get("product") or path.stem
            count = sum(1 for item in payload.get("review_required_claims", []) if item.get("status") == "pending")
            if count:
                counts.setdefault(name, {}).setdefault("review_claim_count", 0)
                counts[name]["review_claim_count"] += count

    for name, rel_path in {"公司": "company/company.json", "标准": "standards/standards.json", "市场": "market/market.json"}.items():
        path = root / config.packs_dir / rel_path
        if not path.exists():
            continue
        payload = json.loads(path.read_text(encoding="utf-8"))
        count = sum(1 for item in payload.get("review_required_items", []) if item.get("status") == "pending")
        if count:
            counts.setdefault(name, {}).setdefault("review_claim_count", 0)
            counts[name]["review_claim_count"] += count


def compute_partition_fingerprint(root: Path, config: ProjectConfig, partition: BuildPartition) -> dict[str, Any]:
    paths: list[Path] = []
    if partition.type == "product":
        paths.extend([resolve_project_path(root, partition.raw_path), resolve_raw_dir(root, config) / "00_知识库核心资料"])
    else:
        paths.append(resolve_project_path(root, partition.raw_path))

    files = []
    for base in paths:
        if not base.exists():
            continue
        for path in sorted(base.rglob("*")):
            if not path.is_file() or path.name == ".DS_Store":
                continue
            files.append(
                {
                    "path": source_path(root, path),
                    "sha256": sha256_file(path),
                }
            )
    digest = hashlib.sha256(json.dumps(files, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()
    return {"partition": partition.name, "files": files, "digest": digest}


def fingerprint_has_changed(root: Path, config: ProjectConfig, partition: BuildPartition, fingerprint: dict[str, Any]) -> bool:
    path = partition_fingerprint_path(root, config, partition)
    if not path.exists():
        return False
    previous = json.loads(path.read_text(encoding="utf-8"))
    return previous.get("digest") != fingerprint.get("digest")


def write_partition_fingerprint(root: Path, config: ProjectConfig, partition: BuildPartition, fingerprint: dict[str, Any]) -> None:
    path = partition_fingerprint_path(root, config, partition)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(fingerprint, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def partition_fingerprint_path(root: Path, config: ProjectConfig, partition: BuildPartition) -> Path:
    return root / config.output_dir / "cache" / "build-partitions" / f"{partition.name}.json"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()
