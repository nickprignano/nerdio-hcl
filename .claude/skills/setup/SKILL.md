---
name: setup
description: Interactive setup and configuration guide for Nerdio Manager for Enterprise (nerdio-hcl). Reads schema/parameters.json, runs ./nerdio preflight, and renders tfvars.
---

# Setup Skill (`nerdio-hcl`)

Use this skill when the user wants to configure a new Nerdio Manager for Enterprise + Azure Virtual
Desktop environment or update their deployment answers.

## Workflow

1. **Discover & Schema**:
   - Read `schema/parameters.json` (never invent parameter names outside the schema).
   - Walk through the `discover` phase (`environment`, `cloud`, `identity_model`, `user_count`, `workload`) and explain the defaults derived for `configure`.
2. **Preflight Readiness Check**:
   - Run `./nerdio preflight --stage pre-install` (or `py -X utf8 scripts/nerdio/nerdio.py preflight` on Windows).
   - Explain any `fail`, `warn`, `manual`, or `no-access` results using `docs/knowledge/nerdio/readiness.md`.
   - When quota or PIM roles are flagged, offer `./nerdio fix vcpu`, `./nerdio fix quota`, or `./nerdio fix roles`.
3. **Render Configuration**:
   - Run `./nerdio init` (or `./nerdio init --answers <file> --non-interactive`) to validate answers and render `setup.auto.tfvars.json` for Stage 1 (`01-platform`) and Stage 2 (`02-nerdio-config`).

## Guardrails

- Never ask for, display, or store secrets, passwords, or real tenant/subscription IDs in tracked files.
