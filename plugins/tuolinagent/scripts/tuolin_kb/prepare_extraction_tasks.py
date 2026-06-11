#!/usr/bin/env python3
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from tuolin_kb.config import load_project_config
from tuolin_kb.extraction import create_extraction_tasks, write_pending_extraction_tasks


def main() -> int:
    root = Path(".").resolve()
    config = load_project_config(root)
    tasks = create_extraction_tasks(root, config=config)
    task_path = write_pending_extraction_tasks(root, tasks, config=config)
    print(f"素材分析清单: {task_path}")
    print(f"待分析素材数量: {len(tasks)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
