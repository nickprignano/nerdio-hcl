"""Unit tests for the read-only Nerdio MCP server (scripts/mcp/nerdio_mcp.py)."""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import nerdio_mcp  # noqa: E402


class McpServerTests(unittest.TestCase):
    def test_initialize_and_tools_list(self):
        init = nerdio_mcp.handle_request({"jsonrpc": "2.0", "id": 1, "method": "initialize"})
        self.assertEqual(init["result"]["serverInfo"]["name"], "nerdio-hcl-mcp")
        tools = nerdio_mcp.handle_request({"jsonrpc": "2.0", "id": 2, "method": "tools/list"})
        names = [t["name"] for t in tools["result"]["tools"]]
        self.assertEqual(names, ["nerdio_readiness_catalogue", "nerdio_kb_search", "nerdio_schema_parameters"])

    def test_readiness_catalogue_tool(self):
        resp = nerdio_mcp.handle_request({
            "jsonrpc": "2.0",
            "id": 3,
            "method": "tools/call",
            "params": {"name": "nerdio_readiness_catalogue", "arguments": {"feature": "insights"}},
        })
        self.assertFalse(resp["result"]["isError"])
        items = json.loads(resp["result"]["content"][0]["text"])
        ids = [i["id"] for i in items]
        self.assertIn("ins.workspace", ids)
        self.assertIn("sub.app_service", ids)

    def test_kb_search_tool(self):
        resp = nerdio_mcp.handle_request({
            "jsonrpc": "2.0",
            "id": 4,
            "method": "tools/call",
            "params": {"name": "nerdio_kb_search", "arguments": {"query": "ansible"}},
        })
        self.assertFalse(resp["result"]["isError"])
        items = json.loads(resp["result"]["content"][0]["text"])
        self.assertTrue(any("0028" in i.get("path", "") for i in items))

    def test_schema_parameters_tool(self):
        resp = nerdio_mcp.handle_request({
            "jsonrpc": "2.0",
            "id": 5,
            "method": "tools/call",
            "params": {"name": "nerdio_schema_parameters", "arguments": {"id": "cloud"}},
        })
        self.assertFalse(resp["result"]["isError"])
        items = json.loads(resp["result"]["content"][0]["text"])
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["id"], "cloud")


if __name__ == "__main__":
    unittest.main()
