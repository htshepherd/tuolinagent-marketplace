#!/usr/bin/env python3
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from tuolin_kb.config import load_project_config
from tuolin_kb.extraction import create_extraction_tasks, write_pending_extraction_tasks
from tuolin_kb.generate_agent_packs import generate_agent_packs
from tuolin_kb.graphify_runner import build_graph


def main() -> int:
    config = load_project_config(".")
    result = build_graph(".", update=False, config=config)
    output = generate_agent_packs(".", config=config)
    tasks = create_extraction_tasks(".", config=config)
    task_path = write_pending_extraction_tasks(".", tasks, config=config)
    print(result.message)
    print(f"graph.json: {result.graph_path}")
    print(f"GRAPH_REPORT.md: {result.report_path}")
    print(f"Agent知识包: {output.packs_dir}")
    print(f"产品数量: {output.product_count}")
    print(f"素材分析清单: {task_path}")
    print(f"待分析素材数量: {len(tasks)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
