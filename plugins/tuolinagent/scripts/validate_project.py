#!/usr/bin/env python3
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tuolin_kb.config import load_project_config
from tuolin_kb.project import validate_project


def main() -> int:
    config = load_project_config(".")
    report = validate_project(".", config=config)
    print(f"项目根目录: {report.root}")
    print(f"Python: {report.python_version}")
    print(f"raw目录: {'存在' if report.raw_exists else '缺失'}")
    print(f"知识库核心资料: {'存在' if report.core_knowledge_exists else '缺失'}")
    print(f"核心资料文件数: {report.core_knowledge_file_count}")
    print(f"Graphify: {'可用' if report.graphify_available else '未检测到'}")
    print(f"ffmpeg: {'可用' if report.ffmpeg_available else '未检测到'}")
    print(f"graphify-out git忽略: {'是' if report.graphify_out_ignored else '否'}")
    print(f"默认视觉模型: {config.default_vision_model}")
    print(f"升级复核模型: {config.escalation_vision_model}")
    if report.warnings:
        print("\n警告:")
        for warning in report.warnings:
            print(f"- {warning}")
    return 0 if report.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
