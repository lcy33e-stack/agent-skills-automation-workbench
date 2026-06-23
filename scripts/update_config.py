from __future__ import annotations

import argparse
import json
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT / "config" / "sources.yml"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--keywords", required=True)
    args = parser.parse_args()

    keywords = [item.strip() for item in json.loads(args.keywords) if item and item.strip()]
    if not keywords:
        raise SystemExit("keywords cannot be empty")

    data = yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))
    data.setdefault("settings", {})["keywords"] = keywords
    CONFIG_PATH.write_text(
        yaml.safe_dump(data, allow_unicode=True, sort_keys=False, width=1000),
        encoding="utf-8",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
