---
name: troubleshoot
description: Diagnose Nerdio Manager, Azure Virtual Desktop, FSLogix, Private Link, and Terraform state issues using the knowledge base and read-only readiness engine.
---

# Troubleshoot Skill (`nerdio-hcl`)

Use this skill when diagnosing deployment failures, unhealthy session hosts, FSLogix profile mount
errors, or Nerdio Manager health issues.

## Workflow

1. **Run Targeted Readiness Checks**:
   - Pre-install: `./nerdio preflight --stage pre-install`
   - Post-install: `./nerdio preflight --stage post-install --resource-group <rg>`
   - Post-wizard: `./nerdio preflight --stage post-wizard --features all`
2. **Consult Knowledge Base**:
   - Search the knowledge base (the `nerdio_kb_search` tool of the kit's MCP server, or `docs/knowledge/README.md`) and `docs/knowledge/troubleshooting/README.md` for known error slugs (for example, `smart-detection-action-group-blocks-destroy`).
   - Check `avd.host_health` output for failing session host health checks (`DomainJoinedCheck`, `FSLogixNotHealthy`, `SxSStackListenerNotReady`).
3. **Log Findings**:
   - When a new verified behavior or error is discovered, draft a sanitized finding for a KB feedback or known-error issue (`.github/ISSUE_TEMPLATE/`), following `docs/guardrails.md`; pass any output through `./nerdio redact` first.
