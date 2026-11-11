---
status: accepted
date: 2026-11-10
decision-makers: [maintainers]
---

# 0031. AI tools in the kit are read-only by default, with an allowlist CI enforces

## Context and Problem Statement

The kit already has a setup chat, Claude Code skills, `AGENTS.md`, `llms.txt` and a small MCP server
over its own files. Microsoft's Azure MCP Server can give an assistant live Azure reads, including
AVD host pools and session hosts, and Nerdio Manager now has a read-only MCP connector in preview.
Both make the verify and troubleshoot phases far better, but the Azure server can also create and
delete resources and return secret values, and its npm `latest` tag points at a beta. How should
the kit let AI assistants use these tools without weakening the guardrails?

## Considered Options

- Leave MCP to each user's own configuration
- Ship the Azure MCP Server with its defaults (all namespaces, read and write)
- Ship it read-only, pinned and limited to a namespace allowlist, with CI guarding the config
- Host a remote Azure MCP Server for the setup chat

## Decision Outcome

Chosen option: "Ship it read-only, pinned and limited to a namespace allowlist", because it gives
Claude Code live reads from Cloud Shell with no new rights, no install and no listener, and a test
stops a later PR from quietly widening it.

- `.mcp.json` runs `@azure/mcp` at an exact stable version with `--read-only` and an explicit
  `--namespace` list. Namespaces with read tools that return secrets or send tenant data to model
  sampling (`keyvault`, `appservice`, `insights`) are refused, as are `storage` and `sreagent`.
- No `--dangerously-*` options, no `--tool`, stdio only, no credentials in the file.
- Claude Code's project settings deny `terraform apply` and `destroy`, `./nerdio assistant`,
  `./nerdio fix`, the pipeline's apply step and Azure deletes, matching guardrail 6.
- The kit's own MCP tools carry MCP read-only annotations.
- `scripts/mcp/test_mcp_config.py` checks all of this, and that the commands and paths named in
  skills, `AGENTS.md`, the chat prompt and `docs/ai.md` exist.
- The setup chat doesn't call MCP servers: the Claude API's MCP connector needs a public endpoint
  and a forwarded token. Its verify phase gets narrow read-only tools instead.
- Nerdio's MCP connector stays optional and per user until a personal-sandbox spike confirms its
  sign-in and that it's read-only.

### Consequences

- Good, because assistants can check host pools, session hosts, health, quota, policy and role
  assignments against the plan without anyone granting new rights.
- Good, because widening the allowlist or unpinning the server is a reviewed change with a failing test.
- Bad, because read-only filters tools, not the signed-in identity: someone with active PIM
  roles still runs reads as Owner. The docs say to investigate as Reader.
- Bad, because the pin needs bumping by hand.

## More Information

- [docs/ai.md](../../ai.md): surfaces, boundaries and the build plan.
- Azure MCP Server [start options](https://learn.microsoft.com/azure/developer/azure-mcp-server/tools/#azure-mcp-server-start-parameters)
  and [AVD tools](https://learn.microsoft.com/azure/developer/azure-mcp-server/tools/azure-virtual-desktop).
- Revisit when the Nerdio connector spike is done, or when the chat needs reads the readiness
  engine can't give.
