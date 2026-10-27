"""Keep the repository's top-level docs in sync with the codebase and knowledge base.

  - Generates the Layout block in README.md from the actual modules/, environments/example/ and
    docs/ directories (between BEGIN/END GENERATED comments).
  - Checks that every module in modules/, stage in environments/example/ and doc in docs/*.md has
    a description and is listed in README.md.
  - Checks relative links, #heading anchors and leak patterns (emails, public IPs) across all
    non-KB Markdown files (scripts/kb/validate.py covers docs/knowledge/ and llms.txt).
  - Checks that docs do not cite superseded decision records without also naming the superseding
    decision, and that docs/architecture.md names the active core and config modules.
"""

from __future__ import annotations

import ipaddress
import re
from pathlib import Path

from engine import ROOT

README = ROOT / "README.md"
ARCHITECTURE = ROOT / "docs" / "architecture.md"
DECISIONS_DIR = ROOT / "docs" / "knowledge" / "decisions"

BEGIN = "<!-- BEGIN GENERATED: layout (./nerdio docs --write) -->"
END = "<!-- END GENERATED: layout -->"

# Ordered module descriptions; check_inventory() verifies this matches modules/* on disk.
MODULES: dict[str, str] = {
    "foundation": "resource groups, providers, Log Analytics",
    "network": "AVD spoke network and private DNS",
    "fslogix-storage": "profile storage",
    "anf-storage": "optional Azure NetApp Files high-IOPS SMB profile volume",
    "nerdio-core": "Nerdio Manager built in Terraform, plus the app code deploy job (default)",
    "nerdio-manager": "Azure Marketplace resource discovery + optional template deployment",
    "nerdio-identity": "Nerdio's Entra app, app roles, consent and REST API client",
    "nerdio-secrets": "Key Vault hand-off of the REST API secret to stage 2 (default)",
    "openbao": "optional OpenBao server that mints a short-lived REST API secret per run",
    "nerdio-hardening": "private endpoints and VNet integration for Nerdio's core resources",
    "automation-workers": "optional Hybrid Runbook Worker VM Scale Set inside the AVD VNet",
    "avd-insights": "optional AVD Insights Data Collection Rule, alerts and consumption budget",
    "cmk-encryption": "optional Customer-Managed Key encryption and per-region Disk Encryption Sets",
    "nerdio-rbac": "optional custom least-privilege Azure RBAC role for Nerdio Manager",
    "vnet-runner": "optional ephemeral GitHub Actions runner inside the AVD VNet",
    "image-gallery": "Compute Gallery and image definitions for Packer",
    "nerdio-config": "Nerdio objects through the nerdio/nme provider",
    "nerdio-rest-gaps": "Nerdio REST API endpoints not yet covered by nerdio/nme",
    "intune-policies": "optional Intune update rings and Defender exclusions via Microsoft Graph",
    "windows-365": "optional Windows 365 Cloud PC provisioning alongside Nerdio Manager",
    "azure-local": "optional Azure Local logical network and RBAC for hybrid AVD host pools",
    "deploy-pipeline": "state storage, OIDC deploy identities and the GitHub approval gate",
    "assistant": "self-hosted setup chatbot (Container App, Entra sign-in, Claude / Foundry)",
    "github-settings": "repository settings, rulesets and labels declared in Terraform",
}

# Ordered stage descriptions; check_inventory() verifies this matches environments/example/* on disk.
STAGES: dict[str, str] = {
    "00-assistant": "optional self-hosted setup chatbot",
    "00-pipeline": "one-time bootstrap for the deploy pipeline",
    "01-platform": "stage 1 root: Azure + Entra + Nerdio install",
    "02-nerdio-config": "stage 2 root: Nerdio configuration via nerdio/nme",
}

# Ordered top-level docs; check_inventory() verifies this matches docs/*.md on disk.
DOCS: dict[str, str] = {
    "guardrails.md": "non-negotiable security, browser and license rules",
    "setup.md": "guided setup across chat, CLI and the Actions form",
    "assistant.md": "deploying and connecting the self-hosted setup chatbot",
    "deployment-runbook.md": "end-to-end order of operations and manual wizard steps",
    "pipeline.md": "plan and apply from GitHub Actions behind an approval",
    "access.md": "every Azure, Entra, GitHub and Anthropic right the kit needs",
    "secrets.md": "how stage 2 gets the REST API secret without anyone handling it",
    "cloud-shell.md": "running from Azure Cloud Shell in any browser",
    "codespaces.md": "VS Code in the browser as an optional workbench",
    "architecture.md": "diagram and design decisions across stages",
    "model-pilot.md": "measuring and reporting the model-selection pilot",
}

CODE_FENCE = re.compile(r"```.*?```", re.S)
INLINE_CODE = re.compile(r"`[^`\n]+`")
HEADING = re.compile(r"^#{1,6}\s+(.+?)\s*$", re.M)
LINK = re.compile(r"(?<!!)\[[^\]]*\]\(([^)\s]+)(?:\s+\"[^\"]*\")?\)")
EMAIL = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")
IPV4 = re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b")
ALLOWED_EMAIL_DOMAINS = ("example.com", "contoso.com", "users.noreply.github.com")
DOC_IP_RANGES = tuple(ipaddress.ip_network(r) for r in ("192.0.2.0/24", "198.51.100.0/24", "203.0.113.0/24"))


def layout_block() -> str:
    lines = [
        BEGIN,
        "```",
        "modules/",
    ]
    for name, desc in MODULES.items():
        col = f"{name}/"
        lines.append(f"  {col:<19}{desc}")
    lines += [
        "environments/",
        "  example/",
    ]
    for name, desc in STAGES.items():
        col = f"{name}/"
        lines.append(f"    {col:<19}{desc}")
    lines += [
        "assistant/             setup chatbot app and prompt (deployed by 00-assistant)",
        "schema/                parameters.json single source of truth + example answer sets",
        "packer/",
        "  avd-win11/           Windows 11 multi-session image build",
        "ansible/               optional image and hybrid AD DS playbooks (decision 0028)",
        "github/                this repository's own GitHub settings in Terraform",
        "templates/",
        "  nerdio-manager/      exported Marketplace template (marketplace install only)",
        "docs/",
    ]
    for name, desc in DOCS.items():
        lines.append(f"  {name:<23}{desc}" if desc else f"  {name}")
    lines += [
        "  knowledge/           the living knowledge base and decision records",
        "```",
        END,
    ]
    return "\n".join(lines)


def readme_in_sync(path: Path = README) -> bool:
    text = path.read_text(encoding="utf-8") if path.exists() else ""
    return layout_block() in text


def write_readme(path: Path = README) -> bool:
    text = path.read_text(encoding="utf-8")
    pattern = re.compile(re.escape(BEGIN) + r".*?" + re.escape(END), re.S)
    if not pattern.search(text):
        raise ValueError(f"{path} has no {BEGIN} markers")
    new = pattern.sub(lambda _: layout_block(), text)
    if new == text:
        return False
    path.write_text(new, encoding="utf-8")
    return True


def check_inventory(root: Path = ROOT) -> list[str]:
    problems: list[str] = []
    actual_modules = {p.name for p in (root / "modules").iterdir() if p.is_dir()}
    for m in sorted(actual_modules - set(MODULES)):
        problems.append(f"modules/{m} is not listed in scripts/nerdio/docs.py MODULES")
    for m in sorted(set(MODULES) - actual_modules):
        problems.append(f"scripts/nerdio/docs.py MODULES lists missing module modules/{m}")

    actual_stages = {p.name for p in (root / "environments" / "example").iterdir() if p.is_dir()}
    for s in sorted(actual_stages - set(STAGES)):
        problems.append(f"environments/example/{s} is not listed in scripts/nerdio/docs.py STAGES")
    for s in sorted(set(STAGES) - actual_stages):
        problems.append(f"scripts/nerdio/docs.py STAGES lists missing stage environments/example/{s}")

    actual_docs = {p.name for p in (root / "docs").glob("*.md") if p.is_file()}
    for d in sorted(actual_docs - set(DOCS)):
        problems.append(f"docs/{d} is not listed in scripts/nerdio/docs.py DOCS")
    for d in sorted(set(DOCS) - actual_docs):
        problems.append(f"scripts/nerdio/docs.py DOCS lists missing file docs/{d}")
    return problems


def _strip_code(text: str) -> str:
    return INLINE_CODE.sub("", CODE_FENCE.sub("", text))


def _anchors(body: str) -> set[str]:
    seen: dict[str, int] = {}
    out: set[str] = set()
    for raw in HEADING.findall(CODE_FENCE.sub("", body)):
        clean = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", raw).replace("`", "")
        slug = re.sub(r"[^\w\s-]", "", clean.lower()).strip()
        slug = re.sub(r"\s+", "-", slug)
        n = seen.get(slug, 0)
        seen[slug] = n + 1
        out.add(slug if n == 0 else f"{slug}-{n}")
    return out


def repo_markdown_files(root: Path = ROOT) -> list[Path]:
    """Every tracked-style Markdown file outside docs/knowledge/ (which scripts/kb/validate.py checks)."""
    kb = (root / "docs" / "knowledge").resolve()
    out: list[Path] = []
    for p in sorted(root.rglob("*.md")):
        resolved = p.resolve()
        if any(part.startswith(".") and part not in (".github", ".claude") for part in p.relative_to(root).parts):
            continue
        if kb in resolved.parents:
            continue
        out.append(p)
    return out


def check_links_and_leaks(files: list[Path] | None = None, root: Path = ROOT) -> list[str]:
    problems: list[str] = []
    for path in (files if files is not None else repo_markdown_files(root)):
        rel_path = path.relative_to(root).as_posix()
        text = path.read_text(encoding="utf-8")
        searchable = _strip_code(text)
        for m in LINK.finditer(searchable):
            target = m.group(1)
            if re.match(r"^[a-z]+:", target):
                continue
            file_part, _, anchor = target.partition("#")
            dest = (path.parent / file_part).resolve() if file_part else path.resolve()
            if not dest.exists():
                problems.append(f"{rel_path}: broken link {target!r}")
                continue
            if anchor and dest.suffix == ".md":
                dest_text = dest.read_text(encoding="utf-8")
                if dest_text.startswith("---\n"):
                    _, _, dest_text = dest_text[4:].partition("\n---\n")
                if anchor not in _anchors(dest_text):
                    problems.append(f"{rel_path}: link {target!r} has no heading #{anchor}")
        for line_no, line in enumerate(text.splitlines(), 1):
            for m in EMAIL.finditer(line):
                if not m.group(0).lower().endswith(ALLOWED_EMAIL_DOMAINS):
                    problems.append(f"{rel_path}:{line_no}: non-placeholder email address")
            for m in IPV4.finditer(line):
                try:
                    ip = ipaddress.ip_address(m.group(0))
                except ValueError:
                    continue
                if ip.is_global and not any(ip in net for net in DOC_IP_RANGES):
                    problems.append(f"{rel_path}:{line_no}: public IP {ip}")
    return problems


def superseded_decisions(decisions_dir: Path = DECISIONS_DIR) -> dict[str, str]:
    """Map of decision filename -> superseding decision number (e.g. '0003-marketplace-template.md': '0011')."""
    out: dict[str, str] = {}
    if not decisions_dir.exists():
        return out
    for p in sorted(decisions_dir.glob("[0-9][0-9][0-9][0-9]-*.md")):
        text = p.read_text(encoding="utf-8")
        if not text.startswith("---\n"):
            continue
        fm, _, _ = text[4:].partition("\n---\n")
        m = re.search(r"^status:\s*superseded by (\d{4})\s*$", fm, re.M)
        if m:
            out[p.name] = m.group(1)
    return out


def check_decisions_and_architecture(root: Path = ROOT) -> list[str]:
    problems: list[str] = []
    superseded = superseded_decisions(root / "docs" / "knowledge" / "decisions")
    check_files = [root / "README.md", *sorted((root / "docs").glob("*.md"))]
    for path in check_files:
        if not path.exists():
            continue
        text = path.read_text(encoding="utf-8")
        rel_path = path.relative_to(root).as_posix()
        for dec_file, replacement in superseded.items():
            if dec_file in text and replacement not in text:
                problems.append(
                    f"{rel_path}: cites superseded decision {dec_file} without mentioning decision {replacement}"
                )
    arch = root / "docs" / "architecture.md"
    if arch.exists():
        arch_text = arch.read_text(encoding="utf-8")
        for required in ("modules/nerdio-core", "modules/nerdio-config"):
            if required not in arch_text:
                problems.append(f"docs/architecture.md: missing reference to active module {required}")
    return problems


def check(root: Path = ROOT) -> list[str]:
    problems = check_inventory(root)
    readme = root / "README.md"
    if readme.exists() and not readme_in_sync(readme):
        problems.append("README.md layout is out of date; run ./nerdio docs --write")
    problems += check_links_and_leaks(root=root)
    problems += check_decisions_and_architecture(root=root)
    return problems
