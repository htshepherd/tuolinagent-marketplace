#!/usr/bin/env python3
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from tuolin_kb.qa import answer_question


def main() -> int:
    question = " ".join(sys.argv[1:]).strip()
    if not question:
        print("用法: python3 scripts/tuolin_kb/query.py \"石英纤维隔热带适合室内排烟管吗？\"")
        return 2
    result = answer_question(Path("."), question)
    print(result.answer)
    if result.sources:
        print("\n来源:")
        for source in result.sources:
            print(f"- {source}")
    return 0 if result.answered else 1


if __name__ == "__main__":
    raise SystemExit(main())
