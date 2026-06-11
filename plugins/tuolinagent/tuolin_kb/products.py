from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

from .config import ProjectConfig
from .constants import CORE_PRODUCTS, IMAGE_SUFFIXES, REPORT_SUFFIXES, VIDEO_SUFFIXES, CoreProduct
from .document_conversion import markdown_path_for_pdf
from .paths import resolve_raw_dir, source_path


@dataclass(frozen=True)
class ProductAssets:
    product_dir: str | None
    reports: tuple[str, ...] = ()
    report_texts: tuple[str, ...] = ()
    images: tuple[str, ...] = ()
    videos: tuple[str, ...] = ()

    @property
    def has_report_images_videos(self) -> bool:
        return bool(self.reports and self.images and self.videos)

    @property
    def has_any_assets(self) -> bool:
        return bool(self.reports or self.images or self.videos)

    @property
    def product_dir_exists(self) -> bool:
        return self.product_dir is not None


@dataclass(frozen=True)
class ProductKnowledge:
    product: CoreProduct
    facts: dict[str, object]
    assets: ProductAssets
    status: str
    asset_status: str
    review_required: bool = False
    inferred_claims: tuple[str, ...] = field(default_factory=tuple)


def collect_product_knowledge(root: Path, config: ProjectConfig) -> list[ProductKnowledge]:
    raw_dir = resolve_raw_dir(root, config)
    core_text = read_core_knowledge(raw_dir / "00_知识库核心资料")
    table_rows = parse_product_rows(core_text)
    return [build_product_knowledge(root, config, product, core_text, table_rows) for product in CORE_PRODUCTS]


def read_core_knowledge(core_dir: Path) -> str:
    if not core_dir.exists():
        return ""
    chunks = []
    for path in sorted(core_dir.iterdir()):
        if path.is_file() and path.suffix.lower() in {".md", ".txt"} and path.name != ".DS_Store":
            chunks.append(path.read_text(encoding="utf-8", errors="ignore"))
    return "\n\n".join(chunks)


def parse_product_rows(text: str) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped.startswith("|") or "---" in stripped or "材料" in stripped and "极限耐温" in stripped:
            continue
        cells = [cell.strip().strip("*") for cell in stripped.strip("|").split("|")]
        if len(cells) < 8:
            continue
        rows.append(
            {
                "材料": cells[0],
                "市场名称": cells[1],
                "颜色": cells[2],
                "现货规格": cells[3],
                "单重": cells[4],
                "极限耐温": cells[5],
                "长期使用温度": cells[6],
                "隔热效果": cells[7],
                "核心定位": cells[8] if len(cells) > 8 else "",
            }
        )
    return rows


def build_product_knowledge(
    root: Path,
    config: ProjectConfig,
    product: CoreProduct,
    core_text: str,
    table_rows: list[dict[str, str]],
) -> ProductKnowledge:
    assets = scan_product_assets(root, config, product.name)
    matched_rows = [
        row
        for row in table_rows
        if any(keyword in row.get("材料", "") or keyword in row.get("市场名称", "") for keyword in product.material_keywords)
    ]
    facts = facts_from_rows(product, matched_rows, core_text)

    if not assets.product_dir_exists:
        status = "not_built"
        asset_status = "missing_product_assets"
    elif assets.has_report_images_videos:
        status = "ready"
        asset_status = "has_report_images_videos"
    elif assets.has_any_assets:
        status = "incomplete_assets"
        asset_status = "incomplete_assets"
    else:
        status = "incomplete_assets"
        asset_status = "missing_product_assets"

    return ProductKnowledge(
        product=product,
        facts=facts,
        assets=assets,
        status=status,
        asset_status=asset_status,
        inferred_claims=(),
    )


def scan_product_assets(root: Path, config: ProjectConfig, product_name: str) -> ProductAssets:
    product_root = resolve_raw_dir(root, config) / "04_产品"
    if not product_root.exists():
        return ProductAssets(product_dir=None)

    candidates = [path for path in product_root.iterdir() if path.is_dir() and product_name in path.name]
    if not candidates and product_name == "石英纤维隔热带":
        candidates = [path for path in product_root.iterdir() if path.is_dir() and "石英" in path.name]
    if not candidates:
        return ProductAssets(product_dir=None)

    product_dir = candidates[0]
    reports: list[str] = []
    report_texts: list[str] = []
    images: list[str] = []
    videos: list[str] = []
    for path in sorted(product_dir.rglob("*")):
        if not path.is_file() or path.name == ".DS_Store":
            continue
        relative = source_path(root, path)
        suffix = path.suffix.lower()
        if suffix in REPORT_SUFFIXES:
            reports.append(relative)
            if suffix == ".pdf":
                markdown_path = markdown_path_for_pdf(path)
                if markdown_path.exists():
                    report_texts.append(source_path(root, markdown_path))
            elif suffix in {".md", ".txt"}:
                report_texts.append(relative)
        elif suffix in IMAGE_SUFFIXES:
            images.append(relative)
        elif suffix in VIDEO_SUFFIXES:
            videos.append(relative)

    return ProductAssets(
        product_dir=source_path(root, product_dir),
        reports=tuple(reports),
        report_texts=tuple(report_texts),
        images=tuple(images),
        videos=tuple(videos),
    )


def facts_from_rows(product: CoreProduct, rows: list[dict[str, str]], core_text: str) -> dict[str, object]:
    base: dict[str, object] = {
        "品牌": "拓霖TUOLIN" if "拓霖TUOLIN" in core_text else "",
        "产品名称": product.name,
        "材料": product.name.removesuffix("隔热带"),
        "核心卖点": infer_selling_points(product.name, rows, core_text),
        "适用场景": infer_scenarios(product.name, core_text),
        "禁用场景": infer_forbidden_scenarios(product.name, core_text),
        "产品变体": list(product.variants),
    }
    if rows:
        if len(rows) == 1:
            base.update(rows[0])
        else:
            base["变体参数"] = rows
            base.update(combine_variant_rows(rows))
    return base


def combine_variant_rows(rows: list[dict[str, str]]) -> dict[str, str]:
    combined: dict[str, str] = {}
    for key in ["极限耐温", "长期使用温度", "现货规格", "颜色", "隔热效果", "核心定位"]:
        values = []
        for row in rows:
            label = row.get("材料") or row.get("市场名称")
            value = row.get(key, "")
            if value:
                values.append(f"{label}: {value}")
        combined[key] = "；".join(values)
    return combined


def infer_selling_points(product_name: str, rows: list[dict[str, str]], core_text: str) -> list[str]:
    joined = " ".join(row.get("核心定位", "") + " " + row.get("优点", "") for row in rows)
    source = joined + "\n" + core_text
    if "石英" in product_name:
        return [point for point in ["不刺痒", "不冒烟", "无异味", "室内和出口首选"] if point in source]
    if "陶瓷" in product_name:
        return ["耐温最高", "隔热效果高", "适合发红排气管和大货车"]
    if "玄武岩" in product_name:
        return ["经济款", "天然钛金色", "适合不发红排气管"]
    if "高硅氧" in product_name:
        return ["高端", "高温", "高隔热要求场景"]
    return []


def infer_scenarios(product_name: str, core_text: str) -> list[str]:
    if "石英" in product_name:
        return ["室内排烟管", "发动机舱内", "出口外贸", "怕刺痒或怕冒烟场景"]
    if "陶瓷" in product_name:
        return ["发红排气管", "大货车排气管", "高温户外排烟管"]
    if "玄武岩" in product_name:
        return ["不发红排气管", "户外排烟管", "经济型改装"]
    if "高硅氧" in product_name:
        return ["高端车辆", "高温高隔热要求", "游艇、飞机、高端设备"]
    return []


def infer_forbidden_scenarios(product_name: str, core_text: str) -> list[str]:
    forbidden = []
    if "陶瓷" in product_name and re.search(r"陶瓷纤维.{0,12}不能用于电力系统和电缆保温", core_text):
        forbidden.append("电力系统和电缆保温")
    return forbidden
