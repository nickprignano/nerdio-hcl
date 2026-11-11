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
| A Claude chat (claude.ai), with Microsoft's ARM MCP server as a custom connector | One admin, opt-in | Azure Resource Graph, resource reads, costs, and **write tools** | Optional, per user; tested in a personal sandbox |
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

## Optional: Azure from a Claude chat (ARM MCP server, preview)

Microsoft hosts an Azure Resource Manager MCP server at `https://mcp.management.azure.com`
([overview](https://learn.microsoft.com/azure/azure-resource-manager/management/azure-resource-manager-mcp-overview),
[client set-up](https://learn.microsoft.com/azure/azure-resource-manager/management/azure-resource-manager-mcp-other-clients),
[governance](https://learn.microsoft.com/azure/azure-resource-manager/management/azure-resource-manager-mcp-governance),
[repo with the current IDs](https://github.com/Azure/Azure-Resource-Manager-MCP)). Added as a custom connector in claude.ai,
it lets a Claude chat or project query Azure as you, with nothing to run in Cloud Shell.

**It isn't read-only.** Besides Resource Graph queries, resource reads and cost queries, it offers
`create_deployment`, `create_or_update_resource`, `create_or_update_resource_group`,
`execute_resource_action` (which can restart VMs or list storage keys) and `cancel_deployment`.
Decision 0031's allowlist doesn't apply to it, so it's never part of `.mcp.json`. Use it only:

- in a **personal sandbox**, never a production or intake-gated subscription;
- signed in as an account with **Reader** (and no active PIM roles), so the write tools fail;
- with the write tools switched off in the connector's tool settings, where your client offers that.

Microsoft's governance guidance has a sample Azure Policy that denies requests whose caller app ID is
the ARM MCP server's. Assign it in the sandbox if you want Azure, not just the role, to block writes;
Microsoft notes a policy that targets deployments doesn't block every other tool on its own.

Set-up, from Cloud Shell in **Bash** (type `bash` first if the prompt starts with `PS`), signed in to
the sandbox tenant. The app ID and scope ID are Microsoft's published IDs for the ARM MCP server; check its repository
for the current values before you run this.

```bash
ARM=22bfbae3-f4e7-485f-be43-8cee15065084
APP=$(az ad app create --display-name "Claude ARM MCP connector" --web-redirect-uris "https://claude.ai/api/mcp/auth_callback" "https://claude.ai/api/mcp/auth_callback/" --sign-in-audience AzureADMyOrg --query appId -o tsv)
az ad app permission add --id "$APP" --api "$ARM" --api-permissions 601b3b64-a3c4-4faa-ab9c-8f97ba332aa3=Scope
az ad sp show --id "$ARM" >/dev/null 2>&1 || az ad sp create --id "$ARM" >/dev/null
az ad sp create --id "$APP" >/dev/null
az ad app permission admin-consent --id "$APP"
echo "Client ID: $APP"
az ad app credential reset --id "$APP" --display-name claude --end-date "$(date -d '+90 days' +%F)" --query password -o tsv
```

The last line prints a client secret. Paste it and the client ID only into the connector's settings
in claude.ai (Settings, Connectors, Add custom connector, URL `https://mcp.management.azure.com`,
then Advanced), run `clear`, and never paste either into a chat. Then Connect and sign in.

Gotchas from the sandbox test:

- **Redirect URI without the trailing slash.** Microsoft's guide shows
  `https://claude.ai/api/mcp/auth_callback/`, but Claude sends it without the slash, and sign-in
  fails with `AADSTS50011`. The commands above register both.
- **Bash, not PowerShell.** Cloud Shell can open in PowerShell, where every line above fails before
  reaching Azure. Switch with `bash`.
- Admin consent needs Cloud Application Administrator or higher once. The secret expires in 90
  days; reset it the same way and update the connector.
- To remove it: delete the connector in claude.ai, then `az ad app delete --id <client-id>` (you run
  it; Claude Code's settings deny Azure deletes).

## Why the setup chat doesn't use MCP (yet)

The Claude API can call remote MCP servers itself, but only ones it can reach on the public
internet, with a bearer token sent in each request. The chat's Azure access is a managed identity
inside your tenant, and putting an Azure MCP Server on a public URL with a forwarded token would
widen the attack surface for little gain. The chat keeps calling its own narrow tools; when it
needs live reads for the verify phase, they come from the read-only readiness engine (plan step 2),
not an MCP hop.

## Build plan

Each step is a separate PR. Nothing here deploys anything.

1. **Done (PR #68).** Decision 0031, `.mcp.json` with the read-only Azure MCP Server, the guard
   tests in CI, Claude Code deny rules, annotations on the kit's MCP tools, and fixes to skills
   that named commands and files that don't exist.
2. **Done.** Verify without the pipeline. With the pipeline the chat already ran stage `verify`
   and read its results. Without it, the chat now gives a Cloud Shell paste for the read-only
   checks after the install (`--stage post-install`) and after the wizard (`--stage post-wizard`),
   as a masked Markdown report, with optional feature checks such as `ai`. No new Azure rights.
3. **Sandbox spike (personal sandbox only).** Run the Azure MCP Server and Nerdio's MCP connector
   from Claude Code in Cloud Shell on an iPad. Record what works in the KB: the connector's
   sign-in, its tools, whether it's read-only, and Azure MCP's AVD tools against a Nerdio host pool.
4. **Nerdio AI planning inputs.** The chat can already add `--features ai` (Cognitive Services
   provider, model and quota checks) when someone says they plan Nerdio Copilot. Still to do: a
   schema question for it, so the CLI and the Actions form ask too. Turning Copilot on stays a
   Nerdio portal step: there's no API.
5. **Later, only on demand.** A remote Azure MCP Server (Container Apps with on-behalf-of sign-in)
   for clients other than Claude Code. It needs Cloud Application Administrator for consent and a
   new decision first.
