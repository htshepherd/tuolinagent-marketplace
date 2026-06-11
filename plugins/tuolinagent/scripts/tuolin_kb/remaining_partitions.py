#!/usr/bin/env python3
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from tuolin_kb.natural_language import load_remaining_partitions_text


def main() -> int:
    print(load_remaining_partitions_text("."))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
