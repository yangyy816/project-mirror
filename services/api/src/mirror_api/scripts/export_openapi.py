from __future__ import annotations

import json
from pathlib import Path

from mirror_api.main import app


def run() -> None:
    root = Path(__file__).resolve().parents[5]
    output = root / "packages" / "contracts" / "openapi.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(app.openapi(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(output)


if __name__ == "__main__":
    run()
