#!/usr/bin/env python3
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from tuolin_kb.config import load_project_config
from tuolin_kb.generate_agent_packs import generate_agent_packs


def main() -> int:
    config = load_project_config(".")
    output = generate_agent_packs(".", config=config)
    print(f"Agent知识包: {output.packs_dir}")
    print(f"manifest: {output.manifest_path}")
    print(f"产品数量: {output.product_count}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
