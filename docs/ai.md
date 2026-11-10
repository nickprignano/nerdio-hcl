# AI-ready kit

How AI assistants work with this kit, what they may touch, and what's still to build. The rules
come from [decision 0031](knowledge/decisions/0031-ai-tools-read-only-by-default.md) and the
[guardrails](guardrails.md): an assistant reads, explains and prepares changes as pull requests;
a person applies.

## The AI surfaces

| Surface | Who uses it | What it can reach | Status |
|---|---|---|---|
| Setup chat ([assistant.md](assistant.md)) | Admins, in a browser | The kit's own tools (schema, readiness, KB, pipeline) through Claude API workload identity federation | Built |
| Claude Code in Cloud Shell, with [`.mcp.json`](../.mcp.json) | Admins and contributors | Read-only Azure, the kit's repository data, Microsoft Learn | Built (this page) |
| `AGENTS.md`, `CLAUDE.md`, `.claude/skills/`, [`llms.txt`](../llms.txt) | Any coding agent | The repository | Built; CI checks the commands and paths they name |
| Machine-readable inputs and outputs | Any tool | [`schema/parameters.json`](../schema/README.md) for questions; `./nerdio preflight --json` for readiness (`nerdio-readiness/1`) | Built |
| Nerdio Manager MCP connector (preview) | A Nerdio admin's own agent | Live Nerdio data, read-only | Optional, per user; untested |
| Nerdio Copilot, ScriptPro, AnalyticsPro | Nerdio users | Azure OpenAI in your tenant | Nerdio's feature; not on the setup path |

## Claude Code in Cloud Shell

[`.mcp.json`](../.mcp.json) gives Claude Code three MCP servers. Claude Code asks you to approve
project servers the first time you open the repository.

| Server | Runs as | What it does |
|---|---|---|
| `azure` | Microsoft's Azure MCP Server (`@azure/mcp`, pinned), started with `npx` and `--read-only`, limited to the namespaces below | Lists subscriptions, resource groups, AVD host pools, session hosts and user sessions, VMs, Monitor logs and metrics, resource health, quota, policy and role assignments, and Microsoft's Terraform guidance |
| `nme-automation` | `scripts/mcp/nerdio_mcp.py`, Python standard library | The readiness check catalogue, KB search and the parameter schema. Repository files only; no network |
| `microsoft-learn` | Microsoft's hosted Learn MCP endpoint | Grounded Azure, Entra and Intune documentation |

Cloud Shell already has what they need: Node.js and `npx` for `azure`, Python for `nme-automation`,
and your Cloud Shell sign-in, which the Azure MCP Server picks up from the Azure CLI. Nothing to
install beyond Claude Code itself. In GovCloud, run `az cloud set --name AzureUSGovernment` and
`az login` first, as for the rest of the kit.

### Boundaries (CI enforces them: `scripts/mcp/test_mcp_config.py`)

- **Read-only.** `--read-only` hides every tool that changes Azure. Namespaces are an allowlist:
  `subscription`, `group`, `virtualdesktop`, `compute`, `monitor`, `resourcehealth`, `quota`,
  `policy`, `role` and `azureterraformbestpractices`.
- **No secret-returning tools, even read-only ones.** `keyvault` (secret values), `appservice`
  (app settings) and `insights` (sends tenant data to model sampling) are refused, and so are
  `storage` and `sreagent`. Read-only isn't enough on its own: `keyvault secret get` is a read.
- **Pinned.** An exact stable `@azure/mcp` version, never `@latest` (on npm, `latest` currently
  points at a beta). Bump it in a PR after reading the release notes.
- **No `--dangerously-*` options**, no `--tool` (it bypasses the namespace allowlist) and no HTTP
  listener: stdio only.
- **No credentials in `.mcp.json`.** Each server signs in as the person running Claude Code.
- **Claude Code can't apply.** [`.claude/settings.json`](../.claude/settings.json) denies
  `terraform apply` and `destroy`, `./nerdio assistant`, `./nerdio fix`, the pipeline's apply
  step, `az ... delete` and role assignments. Claude prepares the command and explains it; you run it.

### The identity is still yours

`--read-only` limits which tools the server offers, not what your sign-in can do. If you're Owner
with PIM roles active, the tools run as Owner. For investigation, use an account or session with
**Reader** on the subscription and **Log Analytics Reader** for Monitor queries
([access](access.md)), and let PIM roles expire before you start Claude Code.

### Optional: Nerdio's MCP connector

Nerdio Manager has a read-only MCP connector in public preview
([KB](knowledge/nerdio/ai-features.md#the-mcp-connector-public-preview)). Its URL is per
installation, so it isn't in `.mcp.json`. A Nerdio admin who has turned it on can add it to their
own Claude Code configuration:

```bash
claude mcp add --transport http nerdio "https://nmw-app-<instance>.azurewebsites.net/mcp"
```

Untested: the browser sign-in from Cloud Shell, and whether it stays read-only. Treat it as a
verify-phase helper only until the sandbox spike below.

## Why the setup chat doesn't use MCP (yet)

The Claude API can call remote MCP servers itself, but only ones it can reach on the public
internet, with a bearer token sent in each request. The chat's Azure access is a managed identity
inside your tenant, and putting an Azure MCP Server on a public URL with a forwarded token would
widen the attack surface for little gain. The chat keeps calling its own narrow tools; when it
needs live reads for the verify phase, they'll be more of those tools (plan below), not an MCP hop.

## Build plan

Each step is a separate PR. Nothing here deploys anything.

1. **Done in this PR.** Decision 0031, `.mcp.json` with the read-only Azure MCP Server, the guard
   tests in CI, Claude Code deny rules, annotations on the kit's MCP tools, and fixes to skills
   that named commands and files that don't exist.
2. **Verify-phase reads in the setup chat.** Add read-only chat tools that call
   `./nerdio preflight --stage post-wizard --json` and summarise the `nerdio-readiness/1` report,
   so the chat's verify and handover phases work without new Azure rights.
3. **Sandbox spike (personal sandbox only).** Run the Azure MCP Server and Nerdio's MCP connector
   from Claude Code in Cloud Shell on an iPad. Record what works in the KB: the connector's
   sign-in, its tools, whether it's read-only, and Azure MCP's AVD tools against a Nerdio host pool.
4. **Nerdio AI planning inputs.** If Nerdio Copilot is wanted, ask for it in the interview and run
   the existing `ai.*` readiness checks (`--features ai`: Cognitive Services provider, model and
   quota) before the wizard. Turning Copilot on stays a Nerdio portal step: there's no API.
5. **Later, only on demand.** A remote Azure MCP Server (Container Apps with on-behalf-of sign-in)
   for clients other than Claude Code. It needs Cloud Application Administrator for consent and a
   new decision first.
