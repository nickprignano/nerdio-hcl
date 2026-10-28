---
title: "Chat assistant: the white-glove guide"
summary: "What the chat assistant covers across the lifecycle: planning, security review, readiness, troubleshooting and day 2"
topic: roadmap
status: plan
last_reviewed: 2026-10-28
---

# Chat assistant: the white-glove guide

What the kit's chat assistant covers across the whole lifecycle, domain by domain. It
extends the "Guided setup by chat" section of the [roadmap](stack-options.md#guided-setup-by-chat-white-glove)
and follows [decision 0008](decisions/0008-chat-front-door.md) and [decision 0014](decisions/0014-self-hosted-setup-chatbot.md):
chat is the front door, and the engine underneath stays deterministic and usable without AI.
The self-hosted setup chatbot (`assistant/`, `modules/assistant`, `environments/example/00-assistant`),
the Claude Code phase skills (`.claude/skills/`), the read-only Nerdio MCP server (`scripts/mcp/nerdio_mcp.py`)
and the deterministic `./nerdio` engine are built; live trial-tenant end-to-end validation is next
([chatbot-first.md](chatbot-first.md)).

The assistant is a planning advisor, security reviewer, teacher and troubleshooter for the whole
lifecycle, from "what is a subscription" to day-2 image rollouts. It works through the
deterministic engine (`./nerdio` commands, Terraform, the workflows). It never replaces it.

## Principles

- **Grounded, not improvised.** Every recommendation cites a source: the kit's knowledge base
  (this folder), Microsoft Learn (through the Microsoft Learn MCP server), Nerdio's help center,
  or Nerdio's own repos. When it can't cite one, it says so. The KB is the curated layer, and the
  weekly curator keeps it current.
- **Decide, record, apply.** Each planning conversation ends in two artifacts:
  - A decision in the environment's decision log, with the choice, the reason and the alternatives considered.
  - The matching tfvars change, opened as a PR.
  Both are local or private, never in the public repo (no-leak rule).
- **Checks are scripts, and chat explains them.** Readiness, quota, security and health checks are
  deterministic commands (`./nerdio preflight`, `check`, `review`). The assistant runs them,
  interprets the results and proposes fixes, so the results don't depend on the model.
- **Teach at the user's level.** It asks once how familiar the user is with Azure, Entra and AVD,
  then explains concepts at that depth and links the source for more.
- **Safe by default.** Secrets never go through chat. Nothing is applied without a plan summary and
  an explicit yes. Write actions against Nerdio or Azure go through workflows, not ad-hoc calls.

## Capability map

These nine lifecycle domains are served by the self-hosted setup chatbot (`assistant/prompt.md`) and
the five phase skills in `.claude/skills/` (`setup`, `deploy`, `image`, `troubleshoot` and `handover`).
Each section lists the decisions the assistant guides, what it checks, and where Nerdio ties in.

### 1. Azure foundations (teaching)
- **Concepts:** tenants, subscriptions, management groups, resource groups, regions and zones,
  VNets and subnets, Azure RBAC versus Entra roles, Azure Policy, tags and cost.
- **Output:** a one-page map of the user's environment as the kit will build it.
- **Nerdio tie-in:** what Nerdio deploys (App Service, SQL, Key Vault, Automation) and what it manages
  afterwards (linked resource groups, networks and subscriptions).

### 2. Network planning
- **Decisions:**
  - Address space and subnets: session hosts, private endpoints, a Bastion option.
  - Outbound internet: NAT gateway, Azure Firewall or a third-party NVA. New subnets no longer get
    default outbound access; *verify the current Microsoft position before stating it as fact*.
  - AVD required URLs and FQDN tags.
  - RDP Shortpath for managed and public networks.
  - DNS and private DNS zones for private endpoints.
  - Hybrid connectivity to domain controllers for AD DS.
- **Checks:** address overlap with peered VNets, reachability of required URLs and DCs, private DNS resolution.
- **Nerdio tie-in:** linked networks (`nme_linked_network`), the kit's private-endpoint hardening
  stage, and Nerdio's RDP Shortpath scripted actions (Get-Nerdio/NMW `scripted-actions/windows-scripts`).

### 3. Identity and access
- **Join model:** Entra-joined, hybrid-joined (AD DS) or Entra Domain Services. The assistant walks
  through the trade-offs: SSO, app compatibility, FSLogix authentication (Entra Kerberos or AD),
  and the Intune or Group Policy path.
- **Authentication:** MFA and Conditional Access for the AVD apps, SSO, and session lock behaviour.
- **Groups design:** user groups per host pool and app group, admin groups, and naming.
- **RBAC:**
  - Least-privilege Azure roles. Nerdio publishes one: `azure-custom-roles/nme-custom-role.json` in Get-Nerdio/NMW.
  - Nerdio's own RBAC, through the users-and-roles API and `nme_user_assignment`.
  - The AVD built-in roles.
  - Break-glass accounts.
- **Checks:** caller roles for bootstrap, group existence, and Conditional Access policies that would
  block sign-in to the AVD app.
- **Nerdio tie-in:** the directory profile, which is the one wizard step without an API, so the
  assistant guides it or runs the Playwright bridge. Also Nerdio app consents, and the REST client app.

### 4. Encryption and VM security
- **Decisions:**
  - Encryption at host (needs a subscription feature registration).
  - Customer-managed keys through disk encryption sets.
  - Trusted Launch or confidential VMs.
  - Storage encryption and private access for FSLogix shares.
  - Key Vault access model.
- **Checks:** feature registration state, VM size support for the chosen security type, gallery
  image compatibility (the kit's Packer image is Gen2 with Trusted Launch).
- **Nerdio tie-in:** host pool `SecurityType` and VM deployment profiles.

### 5. Endpoint management (Intune, ConfigMgr)
- **Decisions:**
  - Intune enrollment for Entra-joined multi-session hosts.
  - Co-management with ConfigMgr, or Group Policy for AD DS.
  - Which baselines to apply: security baseline, ASR, Defender, firewall, compliance.
  - How image-time configuration (Packer) and policy-time configuration (Intune) split the work.
- **Nerdio tie-in:** Nerdio ships ready-made Intune policy sets in Get-Nerdio/NMW `intune-policies/`
  (security baselines, ASR, compliance, Conditional Access, Defender, firewall). The assistant can
  propose them, and Terraform applies them through msgraph or the microsoft365 provider.
  Nerdio's own Intune features are a check-docs item.

### 6. Security review and hardening
- **Inputs:** the planned config before deploy, and the live environment after.
- **Checks, deterministic:**
  - IaC scanning with an open-source scanner (Checkov or Trivy) on the Terraform.
  - The kit's own rules: private endpoints, public access, TLS, diagnostics.
  - Defender for Cloud recommendations and the AVD security baseline.
  - Nerdio hardening options:
    - Private App Service and SQL through the kit's second apply.
    - Screen capture protection and watermarking, through RDP profiles and Nerdio scripted actions.
    - Clipboard and drive redirection.
- **Output:** a findings report ranked by severity, with a "fix it" PR for each finding the kit can
  change. Accepted risks are recorded as decisions.

### 7. Quota and readiness
- **Checks:**
  - vCPU quota per VM family per region, with quota increase guidance.
  - Resource provider registration and region support for every service used.
  - Licenses: the Nerdio license from its Marketplace offer, and AVD user eligibility (*verify the list*).
  - Roles for the bootstrap admin.
  - Required tools in the dev container.
- **Output:** a go/no-go checklist with the exact command or portal link for each fix.

### 8. Deployment troubleshooting
- **Reads:**
  - Terraform plan and apply output, and GitHub Actions logs.
  - Azure activity log and deployment operations.
  - Nerdio job status and tasks (`/api/v1/job/{id}`, `/tasks`).
  - AVD diagnostics (`WVDErrors`, `WVDConnections`).
  - Session host health checks.
- **Method:** match the error against a known-errors catalog in the KB
  ([troubleshooting/](troubleshooting/README.md)), which holds symptom, cause, fix and source for each entry.
  If nothing matches, it proposes a diagnosis with its confidence and the next command to run.
- **Feedback:** each new error a user hits becomes a proposed catalog entry in a PR, so the kit gets
  smarter for the community.

### 9. Post-deployment and day 2+
- **First run:** guide a test sign-in, check FSLogix profile creation, and confirm that auto-scale
  behaves as expected.
- **Day 2:**
  - Add users and groups, add a host pool, change auto-scale.
  - Build and roll out a new image (Packer, then the host pool image, then a scheduled reimage).
  - Update Nerdio itself.
  - Cost review: auto-scale tuning and VM sizing, using Nerdio's cost and usage APIs.
  - Backup and DR for profiles and the Nerdio app.
  - Access reviews.
- **Upkeep:** when the curator's weekly digest flags a breaking provider or Nerdio change, the
  assistant explains the impact on this environment.
- **Output:** the handover runbook, kept current.

## How it's built

- **Self-hosted setup chatbot (`assistant/`, `modules/assistant`, `00-assistant`):** Container App
  with Entra ID sign-in and Claude API workload identity federation (or optional Azure AI Foundry),
  connected to the gated deploy pipeline (`assistant/pipeline.py`).
- **`CLAUDE.md` and `.claude/skills/`:** five lifecycle phase skills (`setup`, `deploy`, `image`,
  `troubleshoot` and `handover`) that cover the nine domains above for Claude Code users.
- **MCP servers (`.mcp.json`):**
  - Microsoft Learn MCP, for grounded Azure, Entra and Intune answers.
  - HashiCorp's Terraform MCP server, for provider docs.
  - The kit's read-only Nerdio MCP server (`scripts/mcp/nerdio_mcp.py`), for live Nerdio state.
- **Deterministic commands and CI checks:** `./nerdio init | preflight | fix | migrate | redact | docs | form | schema check | assistant`,
  plus Trivy IaC scanning in `.github/workflows/validate.yml`.
- **KB backing data:** [`troubleshooting/`](troubleshooting/README.md) (known errors),
  [`security/`](security/README.md) (baselines and accepted-risk patterns), and topic pages linked
  from `schema/parameters.json`.

## Build order inside the chat item of the roadmap

1. **Built:** parameter schema (`schema/parameters.json`), read-only readiness engine (`scripts/nerdio/readiness/`),
   self-hosted chatbot (`assistant/`) and `.claude/skills/setup`.
2. **Built:** identity and multi-region network configuration in `schema/parameters.json`, `modules/network` and `modules/nerdio-identity`.
3. **Built:** `.claude/skills/troubleshoot` and pipeline failure log masking with the seeded `known-errors.yaml` catalog.
4. **Built:** Trivy IaC scanning in CI (`.github/workflows/validate.yml`), `modules/cmk-encryption`, `modules/nerdio-hardening` and `modules/intune-policies`.
5. **Built:** `.claude/skills/deploy`, `image` and `handover`, plus the read-only Nerdio MCP server (`scripts/mcp/nerdio_mcp.py`).

## Must test

- Grounding: answers cite real sources and refuse when no source exists. Check this with a small
  set of graded questions per skill.
- That interview-produced configs pass `terraform validate` and the schema checks.
- Troubleshooting accuracy on recorded failures from live sandbox runs.
- Whether Nerdio's Intune policy JSON can be applied as-is through msgraph or the microsoft365 provider.
