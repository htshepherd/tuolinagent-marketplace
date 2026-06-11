#!/usr/bin/env python3
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from tuolin_kb.review import collect_review_claims, format_review_claims


def main() -> int:
    print(format_review_claims(collect_review_claims(".")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
