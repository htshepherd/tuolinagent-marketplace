#!/usr/bin/env python3
from __future__ import annotations

import json
import shutil
from pathlib import Path


PLUGIN_ROOT = Path(__file__).resolve().parents[1]
MANIFEST_PATH = PLUGIN_ROOT / ".codex-plugin" / "plugin.json"
MARKETPLACE_ROOT = Path.home() / ".agents" / "plugins"
MARKETPLACE_PATH = MARKETPLACE_ROOT / "marketplace.json"

IGNORE_NAMES = {
    ".git",
    ".DS_Store",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    ".venv",
    "venv",
    "env",
    "raw",
    "graphify-out",
}

IGNORE_FILES = {
    "config/tuolin-kb.config.json",
    "config/model-policy.json",
}


def main() -> int:
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    plugin_name = manifest["name"]
    plugin_dir = MARKETPLACE_ROOT / "plugins" / plugin_name

    if plugin_dir.exists():
        shutil.rmtree(plugin_dir)
    shutil.copytree(PLUGIN_ROOT, plugin_dir, ignore=ignore_files)

    marketplace = read_marketplace()
    marketplace["plugins"] = upsert_plugin_entry(marketplace.get("plugins", []), plugin_name)
    MARKETPLACE_ROOT.mkdir(parents=True, exist_ok=True)
    MARKETPLACE_PATH.write_text(json.dumps(marketplace, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print(f"Plugin copied to: {plugin_dir}")
    print(f"Marketplace written to: {MARKETPLACE_PATH}")
    print("")
    print("Next command:")
    print(f"codex plugin add {plugin_name}@{marketplace['name']}")
    print("")
    print("After installing, start a new Codex thread.")
    return 0


def ignore_files(directory: str, names: list[str]) -> set[str]:
    ignored: set[str] = set()
    base = Path(directory)
    for name in names:
        path = base / name
        rel = path.relative_to(PLUGIN_ROOT).as_posix() if path.is_relative_to(PLUGIN_ROOT) else name
        if name in IGNORE_NAMES or rel in IGNORE_FILES or name.endswith(".pyc"):
            ignored.add(name)
    return ignored


def read_marketplace() -> dict:
    if MARKETPLACE_PATH.exists():
        payload = json.loads(MARKETPLACE_PATH.read_text(encoding="utf-8"))
        payload.setdefault("name", "personal")
        payload.setdefault("interface", {"displayName": "Personal"})
        payload.setdefault("plugins", [])
        return payload
    return {
        "name": "personal",
        "interface": {"displayName": "Personal"},
        "plugins": [],
    }


def upsert_plugin_entry(entries: list[dict], plugin_name: str) -> list[dict]:
    entry = {
        "name": plugin_name,
        "source": {
            "source": "local",
            "path": f"./plugins/{plugin_name}",
        },
        "policy": {
            "installation": "AVAILABLE",
            "authentication": "ON_INSTALL",
        },
        "category": "Productivity",
    }
    output = [item for item in entries if item.get("name") != plugin_name]
    output.append(entry)
    return output


if __name__ == "__main__":
    raise SystemExit(main())
