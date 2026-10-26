#!/usr/bin/env python3
"""Read-only Model Context Protocol (MCP) server over stdio for nerdio-hcl.

Standard library only (Python 3.9+). Exposes three read-only tools:
  - nerdio_readiness_catalogue: list registered readiness checks (optionally filtered by stage/feature)
  - nerdio_kb_search: search docs/knowledge/index.json by keyword or topic
  - nerdio_schema_parameters: query schema/parameters.json by phase or parameter id
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Dict, List

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts" / "nerdio"))

import engine  # noqa: E402
from readiness import checks as _checks  # noqa: F401, E402
from readiness.model import REGISTRY  # noqa: E402

SERVER_INFO = {"name": "nerdio-hcl-mcp", "version": "1.0.0"}
PROTOCOL_VERSION = "2024-11-05"

TOOLS: List[Dict[str, Any]] = [
    {
        "name": "nerdio_readiness_catalogue",
        "description": "List read-only readiness checks from the nerdio-hcl registry, optionally filtered by stage or feature.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "stage": {"type": "string", "description": "Filter by stage: pre-install, post-install, or post-wizard"},
                "feature": {"type": "string", "description": "Filter by feature domain (e.g. hardening, rbac, ai, insights)"},
            },
        },
    },
    {
        "name": "nerdio_kb_search",
        "description": "Search the nerdio-hcl knowledge base index (docs/knowledge/index.json) by query text or topic.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Case-insensitive search term matched against title, summary, and path"},
                "topic": {"type": "string", "description": "Optional topic filter (e.g. nerdio, packer, security, decisions)"},
            },
        },
    },
    {
        "name": "nerdio_schema_parameters",
        "description": "List deployment parameters from schema/parameters.json, optionally filtered by phase or parameter id.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "phase": {"type": "string", "description": "Optional phase filter (discover or configure)"},
                "id": {"type": "string", "description": "Optional exact parameter id"},
            },
        },
    },
]


def call_tool(name: str, args: Dict[str, Any]) -> Dict[str, Any]:
    if name == "nerdio_readiness_catalogue":
        stage = args.get("stage")
        feature = args.get("feature")
        rows = []
        for cid in sorted(REGISTRY):
            c = REGISTRY[cid]
            if stage and stage not in c.stages:
                continue
            if feature and feature not in c.features:
                continue
            rows.append({
                "id": c.id,
                "title": c.title,
                "domain": c.domain,
                "stages": list(c.stages),
                "features": list(c.features),
                "needs": c.needs,
                "kb": c.kb,
                "source": c.source,
            })
        return {"content": [{"type": "text", "text": json.dumps(rows, indent=2)}], "isError": False}

    if name == "nerdio_kb_search":
        q = (args.get("query") or "").strip().lower()
        topic = (args.get("topic") or "").strip().lower()
        kb_dir = ROOT / "docs" / "knowledge"
        matches = []
        for md_path in sorted(kb_dir.rglob("*.md")):
            rel_path = md_path.relative_to(ROOT).as_posix()
            text = md_path.read_text(encoding="utf-8")
            first_heading = next((ln.lstrip("# ").strip() for ln in text.splitlines() if ln.startswith("# ")), md_path.stem)
            if topic and topic not in rel_path.lower() and f"topic: {topic}" not in text.lower():
                continue
            haystack = f"{rel_path} {first_heading} {text[:1000]}".lower()
            if not q or q in haystack:
                matches.append({"path": rel_path, "title": first_heading})
        return {"content": [{"type": "text", "text": json.dumps(matches, indent=2)}], "isError": False}

    if name == "nerdio_schema_parameters":
        schema = engine.load_schema()
        phase = args.get("phase")
        pid = args.get("id")
        params = []
        for p in schema.get("parameters", []):
            if phase and p.get("phase") != phase:
                continue
            if pid and p.get("id") != pid:
                continue
            params.append({
                "id": p.get("id"),
                "phase": p.get("phase"),
                "type": p.get("type"),
                "question": p.get("question"),
                "help": p.get("help"),
                "default": p.get("default"),
                "choices": p.get("choices"),
            })
        return {"content": [{"type": "text", "text": json.dumps(params, indent=2)}], "isError": False}

    return {"content": [{"type": "text", "text": f"Unknown tool: {name}"}], "isError": True}


def handle_request(req: Dict[str, Any]) -> Dict[str, Any] | None:
    method = req.get("method", "")
    req_id = req.get("id")
    if req_id is None:
        return None
    if method == "initialize":
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {
                "protocolVersion": PROTOCOL_VERSION,
                "capabilities": {"tools": {}},
                "serverInfo": SERVER_INFO,
            },
        }
    if method == "tools/list":
        return {"jsonrpc": "2.0", "id": req_id, "result": {"tools": TOOLS}}
    if method == "tools/call":
        params = req.get("params") or {}
        result = call_tool(params.get("name", ""), params.get("arguments") or {})
        return {"jsonrpc": "2.0", "id": req_id, "result": result}
    return {
        "jsonrpc": "2.0",
        "id": req_id,
        "error": {"code": -32601, "message": f"Method not found: {method}"},
    }


def main() -> int:
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            req = json.loads(line)
        except json.JSONDecodeError:
            continue
        resp = handle_request(req)
        if resp is not None:
            sys.stdout.write(json.dumps(resp) + "\n")
            sys.stdout.flush()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
