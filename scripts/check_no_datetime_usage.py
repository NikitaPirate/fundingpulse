"""Pre-commit hook that forbids direct datetime usage outside fundingpulse.time."""

from __future__ import annotations

import ast
import sys
from pathlib import Path

ALLOWED_FILES = {
    Path("fundingpulse/time.py"),
}


def main(argv: list[str] | None = None) -> int:
    paths = [Path(raw_path) for raw_path in (argv or sys.argv[1:])]
    violations: list[str] = []

    for path in paths:
        if path.suffix != ".py" or path in ALLOWED_FILES:
            continue

        tree = ast.parse(path.read_text(), filename=str(path))
        violations.extend(_collect_violations(path, tree))

    if violations:
        sys.stderr.write("\n".join(violations) + "\n")
        return 1
    return 0


def _collect_violations(path: Path, tree: ast.AST) -> list[str]:
    violations: list[str] = []

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name == "datetime":
                    violations.append(
                        f"{path}:{node.lineno}: direct 'import datetime' is forbidden; "
                        "use fundingpulse.time"
                    )

        if isinstance(node, ast.ImportFrom) and node.module == "datetime":
            banned_names = {"datetime", "UTC", "timezone"}
            imported = {alias.name for alias in node.names}

            if "*" in imported or banned_names & imported:
                imported_names = ", ".join(sorted(imported))
                violations.append(
                    f"{path}:{node.lineno}: direct datetime import ({imported_names}) "
                    "is forbidden; use fundingpulse.time"
                )

    return violations


if __name__ == "__main__":
    raise SystemExit(main())
