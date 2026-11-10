"""Guard tests for the kit's AI tool boundaries (decision 0031).

They fail CI when a change to `.mcp.json` or `.claude/settings.json` would let an AI assistant
change Azure, read a secret, or pull an unpinned server. Standard library only.
"""

from __future__ import annotations

import json
import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).resolve().parent))

import nerdio_mcp  # noqa: E402

# Azure MCP Server namespaces the kit allows. Each is read-only under --read-only and none has a
# read-only tool that returns secrets (checked against the azmcp command reference for the
# pinned version: tools annotated ReadOnly + Secret live in keyvault, appservice and insights).
AZURE_ALLOWED_NAMESPACES = {
    "subscription", "group", "virtualdesktop", "compute", "monitor", "resourcehealth",
    "quota", "policy", "role", "azureterraformbestpractices",
}
# Namespaces that must never be added, even read-only: they can return secret values
# (keyvault secret get, App Service app settings) or send tenant data to model sampling.
AZURE_DENIED_NAMESPACES = {"keyvault", "appservice", "insights", "storage", "sreagent"}
EXACT_VERSION = re.compile(r"^@azure/mcp@\d+\.\d+\.\d+$")  # no @latest, ranges or prereleases
HTTP_HOSTS = {"learn.microsoft.com"}
SECRETISH = re.compile(r"(KEY|TOKEN|SECRET|PASSWORD|CONNECTION)", re.I)


def load(path: str) -> dict:
    return json.loads((ROOT / path).read_text(encoding="utf-8"))


def option_values(args: list, flag: str) -> list:
    return [args[i + 1] for i, a in enumerate(args[:-1]) if a == flag]


class McpConfigTests(unittest.TestCase):
    def setUp(self):
        self.servers = load(".mcp.json")["mcpServers"]

    def test_only_known_servers(self):
        self.assertEqual(set(self.servers), {"azure", "nerdio-hcl", "microsoft-learn"},
                         "a new MCP server needs a decision-0031 review and a guard here")

    def test_no_secrets_in_config(self):
        for name, server in self.servers.items():
            for key in (server.get("env") or {}):
                self.assertNotRegex(key, SECRETISH, f"{name}: secrets never go in .mcp.json")
            self.assertNotIn("headers", server, f"{name}: no auth headers in the repo")

    def test_azure_is_read_only_pinned_and_allowlisted(self):
        args = self.servers["azure"]["args"]
        self.assertIn("--read-only", args)
        self.assertTrue(any(EXACT_VERSION.match(a) for a in args),
                        "pin @azure/mcp to an exact stable version")
        for a in args:
            self.assertFalse(a.startswith("--dangerously"), a)
        self.assertNotIn("--tool", args, "use --namespace so the allowlist below applies")
        self.assertNotIn("http", option_values(args, "--transport"), "stdio only; no listener")
        namespaces = set(option_values(args, "--namespace"))
        self.assertTrue(namespaces, "an empty namespace list exposes every namespace")
        self.assertLessEqual(namespaces, AZURE_ALLOWED_NAMESPACES)
        self.assertFalse(namespaces & AZURE_DENIED_NAMESPACES)

    def test_http_servers_are_https_and_known(self):
        for name, server in self.servers.items():
            if server.get("type") == "http":
                url = server["url"]
                self.assertTrue(url.startswith("https://"), name)
                self.assertIn(url.split("/")[2], HTTP_HOSTS, name)

    def test_kit_server_tools_are_annotated_read_only(self):
        for tool in nerdio_mcp.TOOLS:
            ann = tool.get("annotations") or {}
            self.assertTrue(ann.get("readOnlyHint"), tool["name"])
            self.assertFalse(ann.get("destructiveHint", True), tool["name"])


class ClaudeSettingsTests(unittest.TestCase):
    def test_assistant_cannot_apply_or_delete(self):
        deny = set(load(".claude/settings.json").get("permissions", {}).get("deny", []))
        for rule in ("Bash(terraform apply:*)", "Bash(terraform destroy:*)",
                     "Bash(terraform * apply*)", "Bash(./nerdio assistant:*)",
                     "Bash(./nerdio fix:*)", "Bash(az * delete*)"):
            self.assertIn(rule, deny)


class AgentInstructionTests(unittest.TestCase):
    """Instructions an agent follows must name commands and files that exist."""

    FILES = sorted((ROOT / ".claude" / "skills").glob("*/SKILL.md")) + [
        ROOT / "AGENTS.md", ROOT / "assistant" / "prompt.md", ROOT / "docs" / "ai.md"]

    def test_nerdio_subcommands_exist(self):
        cli = (ROOT / "scripts" / "nerdio" / "nerdio.py").read_text(encoding="utf-8")
        known = set(re.findall(r'sub\.add_parser\("([a-z-]+)"', cli))
        for path in self.FILES:
            for cmd in re.findall(r"\./nerdio ([a-z][a-z-]*)", path.read_text(encoding="utf-8")):
                self.assertIn(cmd, known, f"{path.relative_to(ROOT)}: ./nerdio {cmd}")

    def test_backticked_repo_paths_exist(self):
        top = {p.name for p in ROOT.iterdir()}  # only refs that start in the repo are paths
        for path in self.FILES:
            for ref in re.findall(r"`((?:\.?[A-Za-z0-9_-]+/)+[A-Za-z0-9_.-]+/?)`",
                                  path.read_text(encoding="utf-8")):
                if "<" in ref or ref.lstrip("./").split("/")[0] not in top:
                    continue
                self.assertTrue((ROOT / ref).exists(), f"{path.relative_to(ROOT)}: {ref}")


if __name__ == "__main__":
    unittest.main()
