#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from tuolin_kb.core_patch import CONFIRM_TOKEN, apply_core_patch, create_core_patch_preview


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="生成或确认核心资料修改预览。")
    parser.add_argument("--claim-index", type=int, help="复核清单中的条目编号，从1开始。")
    parser.add_argument("--preview", action="store_true", help="只生成修改预览，不写入核心资料。")
    parser.add_argument("--patch", help="要确认写入的补丁JSON路径。")
    parser.add_argument("--confirm", help=f"确认写入令牌，必须为 {CONFIRM_TOKEN}。")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    if args.preview:
        if not args.claim_index:
            print("生成修改预览需要传入 --claim-index。")
            return 2
        preview = create_core_patch_preview(".", claim_index=args.claim_index)
        print("已生成核心资料修改预览。现在不会直接改核心资料。")
        print(f"预览文件: {preview.preview_path}")
        print(f"补丁文件: {preview.patch_path}")
        print(f"目标文件: {preview.target_path}")
        print(f"确认写入令牌: {CONFIRM_TOKEN}")
        return 0

    if args.patch:
        if args.confirm != CONFIRM_TOKEN:
            print(f"未写入核心资料：确认写入必须传入 --confirm {CONFIRM_TOKEN}")
            return 2
        result = apply_core_patch(".", patch_path=args.patch, confirm_token=args.confirm)
        print(result.message)
        print(f"核心资料: {result.target_path}")
        print(f"graph.json: {result.graph_path}")
        print(f"manifest.json: {result.manifest_path}")
        return 0 if result.regeneration_succeeded else 3

    print("请使用 --preview --claim-index N 生成修改预览，或使用 --patch PATH --confirm WRITE_CORE_KNOWLEDGE 确认写入。")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
