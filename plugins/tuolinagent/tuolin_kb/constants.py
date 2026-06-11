from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class CoreProduct:
    name: str
    slug: str
    material_keywords: tuple[str, ...]
    variants: tuple[str, ...] = ()


CORE_PRODUCTS: tuple[CoreProduct, ...] = (
    CoreProduct(
        name="陶瓷纤维隔热带",
        slug="ceramic-fiber-insulation-tape",
        material_keywords=("陶瓷纤维", "陶瓷隔热带"),
    ),
    CoreProduct(
        name="石英纤维隔热带",
        slug="quartz-fiber-insulation-tape",
        material_keywords=("石英纤维", "Special Fiberglass"),
    ),
    CoreProduct(
        name="玄武岩纤维隔热带",
        slug="basalt-fiber-insulation-tape",
        material_keywords=("玄武岩纤维", "玄武岩隔热带"),
    ),
    CoreProduct(
        name="高硅氧纤维隔热带",
        slug="high-silica-fiber-insulation-tape",
        material_keywords=("高硅氧纤维", "高硅氧隔热带", "高硅氧背胶隔热带"),
        variants=("有背胶款", "无背胶款"),
    ),
)

STATUS_LABELS = {
    "not_built": "未构建",
    "ready": "可用",
    "incomplete_assets": "素材不完整",
    "needs_update": "需要更新",
    "pending_extraction": "待分析素材",
    "review_required": "需要复核",
}

ASSET_STATUS_LABELS = {
    "missing_product_assets": "缺少产品素材",
    "has_report_images_videos": "报告图片视频齐全",
    "incomplete_assets": "素材不完整",
}

PACK_DIRECTORIES = {
    "product_pack": "products",
    "competitor_pack": "competitors",
    "content_pack": "content",
    "video_pack": "video",
    "evidence_pack": "evidence",
    "readable": "readable",
}

IGNORED_NAMES = {".DS_Store", "__pycache__"}
TEMP_SUFFIXES = {".tmp", ".temp", ".swp", ".part"}
IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp", ".gif", ".bmp", ".tif", ".tiff"}
VIDEO_SUFFIXES = {".mp4", ".mov", ".m4v", ".avi", ".mkv", ".webm"}
REPORT_SUFFIXES = {".pdf", ".doc", ".docx", ".xls", ".xlsx"}
