# Nerdio HCL kit

Terraform and Packer for deploying Nerdio Manager for Enterprise on Azure Virtual Desktop, built
to be turnkey: copy-paste, a button, or a guided chat.

## When someone wants to deploy

You're the guide. Use the `setup` skill (`.claude/skills/setup/`) for discover, prepare and
configure. The phases after that (bootstrap, deploy, wizard steps, verify, handover) are on the
roadmap ([docs/knowledge/chat-assistant.md](docs/knowledge/chat-assistant.md)); until their skills
exist, follow [docs/deployment-runbook.md](docs/deployment-runbook.md) and
[docs/setup.md](docs/setup.md).

`./nerdio` is the engine every front door shares, so the kit works without AI:

| Command | What it does |
|---|---|
| `./nerdio init` | Interview (or `--set name=value`), then write the tfvars after Terraform checks them |
| `./nerdio questions --phase discover\|configure` | The questions as JSON, for chat |
| `./nerdio show` | Current values and where each came from |
| `./nerdio preflight` | Read-only readiness checks: roles, providers, region, VM size, quota |

`schema/parameters.json` is the single source of truth for questions, defaults and validation.

## Rules

- **Grounded answers.** Cite `docs/knowledge/`, Microsoft Learn or Nerdio's docs. Say so when you have no source.
- **No secrets in chat**, and nothing applied without a plan summary and an explicit yes.
- **Public-safe repo.** No tenant or subscription IDs, domains, emails, IP ranges from real networks,
  secrets, or employer or customer names in anything committed. See
  [docs/knowledge/README.md](docs/knowledge/README.md#keep-it-public-safe).
- **HCL first.** If Terraform can do it, Terraform does it. Scripts are thin glue.
- **Works from Azure Cloud Shell (Bash) in a browser.** No local-only tools; read IDs from `az account show`.
- **Every change goes through a PR.** Run `./nerdio schema check` and
  `python3 -m unittest discover -s scripts/nerdio` after touching the schema or engine.
