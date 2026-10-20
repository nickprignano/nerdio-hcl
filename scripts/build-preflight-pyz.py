#!/usr/bin/env python3
"""Build nerdio-preflight.pyz, the standalone readiness check, reproducibly.

  python3 scripts/build-preflight-pyz.py [--out dist/nerdio-preflight.pyz]

The same commit always gives the same bytes (sorted entries, fixed timestamps and modes), so
anyone can rebuild a release and compare its SHA-256 with the published one. The archive holds
the readiness engine, the two kit modules it imports (engine.py for the schema's questions and
defaults, redact.py for masking), a copy of schema/parameters.json, and LICENSE and NOTICE.
"""

from __future__ import annotations

import argparse
import hashlib
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "scripts" / "nerdio"
STAMP = (2020, 1, 1, 0, 0, 0)  # zip can't store dates before 1980; any fixed date works
MAIN = (
    "import sys\n"
    "if sys.version_info < (3, 9):\n"
    "    sys.exit('nerdio-preflight needs Python 3.9 or later; Azure Cloud Shell has it')\n"
    "from readiness.standalone import main_entry\n"
    "main_entry()\n"
)


def members() -> list[tuple[str, bytes]]:
    files = [(f"readiness/{p.relative_to(SRC / 'readiness').as_posix()}", p.read_bytes())
             for p in (SRC / "readiness").rglob("*.py") if "__pycache__" not in p.parts]
    files += [("engine.py", (SRC / "engine.py").read_bytes()), ("redact.py", (SRC / "redact.py").read_bytes()),
              ("readiness/parameters.json", (ROOT / "schema" / "parameters.json").read_bytes()),
              ("LICENSE", (ROOT / "LICENSE").read_bytes()), ("NOTICE", (ROOT / "NOTICE").read_bytes()),
              ("__main__.py", MAIN.encode())]
    return sorted(files)


def build(out: Path) -> str:
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "wb") as f:
        f.write(b"#!/usr/bin/env python3\n")
        with zipfile.ZipFile(f, "w") as z:
            for name, data in members():
                info = zipfile.ZipInfo(name, STAMP)
                info.compress_type = zipfile.ZIP_DEFLATED
                info.external_attr = 0o644 << 16
                info.create_system = 3  # unix, so the mode means the same everywhere
                z.writestr(info, data, compresslevel=9)
    out.chmod(0o755)
    return hashlib.sha256(out.read_bytes()).hexdigest()


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--out", default=str(ROOT / "dist" / "nerdio-preflight.pyz"))
    args = parser.parse_args(argv)
    digest = build(Path(args.out))
    print(f"{digest}  {Path(args.out).name}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
