"""Guard for the repository rename (decision 0035): the old name appears only where it must.

Run: python3 -m unittest discover -s scripts/nerdio
"""

from __future__ import annotations

import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OLD = "nerdio-hcl"

# Accepted decision records are history and keep the name they were written under.
HISTORY = ("docs/knowledge/decisions/",)
# A line may keep the old name only when it says why: a legacy fallback or the old-name signature.
REASONS = ("legacy", "old name")


class RepoNameTests(unittest.TestCase):
    def test_old_name_only_in_history_or_legacy_fallbacks(self):
        files = subprocess.run(["git", "ls-files", "-z"], cwd=ROOT, capture_output=True,
                               text=True, check=True).stdout.split("\0")
        stray = []
        for rel in filter(None, files):
            if rel.startswith(HISTORY) or rel == "scripts/nerdio/test_repo_name.py":
                continue
            try:
                text = (ROOT / rel).read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError):
                continue
            for n, line in enumerate(text.splitlines(), 1):
                if OLD in line and not any(r in line.lower() for r in REASONS):
                    stray.append(f"{rel}:{n}: {line.strip()[:100]}")
        self.assertEqual(stray, [], "rename leftovers; use nme-automation, or say why "
                                    "the old name stays (legacy / old name) on the same line")


if __name__ == "__main__":
    unittest.main()
