#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from tuolin_kb.config import load_project_config
from tuolin_kb.extraction import apply_extraction_results


def main() -> int:
    parser = argparse.ArgumentParser(description="合并Codex素材分析结果")
    parser.add_argument("--partition", help="只合并指定构建分区的结果")
    args = parser.parse_args()
    config = load_project_config(".")
    applied = apply_extraction_results(".", config=config, partition_name=args.partition)
    print(f"已合并素材分析结果: {applied}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
