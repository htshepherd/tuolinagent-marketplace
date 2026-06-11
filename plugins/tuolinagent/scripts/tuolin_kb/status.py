#!/usr/bin/env python3
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from tuolin_kb.status import format_status, load_status


def main() -> int:
    report = load_status(".")
    print(format_status(report))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
