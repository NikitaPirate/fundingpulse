from __future__ import annotations

import json
from pathlib import Path

from fundingpulse.api.main import app


def main() -> None:
    repo_root = Path(__file__).resolve().parent.parent
    output_path = repo_root / "contracts" / "openapi.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(app.openapi(), indent=2, sort_keys=True) + "\n")


if __name__ == "__main__":
    main()
