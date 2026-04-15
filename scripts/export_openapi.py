from __future__ import annotations

import json
import os
from pathlib import Path

# TODO: This is a temporary hack to allow us to export the OpenAPI spec
# without needing to set up a real database connection. In the future, we
# should refactor the code to allow us to export the OpenAPI spec without
# needing to set up any database connection at all.
PLACEHOLDER_DB_ENV = {
    "DB_HOST": "localhost",
    "DB_PORT": "5432",
    "DB_USER": "stub",
    "DB_PASSWORD": "stub",
    "DB_DBNAME": "stub",
}


def main() -> None:
    for key, value in PLACEHOLDER_DB_ENV.items():
        os.environ.setdefault(key, value)

    from fundingpulse.api.main import app

    repo_root = Path(__file__).resolve().parent.parent
    output_path = repo_root / "contracts" / "openapi.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(app.openapi(), indent=2, sort_keys=True) + "\n")


if __name__ == "__main__":
    main()
