---
name: deploy
description: Plan, apply, verify, and manage the two-stage Terraform deployment and gated GitHub Actions pipeline for Nerdio Manager for Enterprise.
---

# Deploy Skill (`nerdio-hcl`)

Use this skill when deploying Stage 1 (`01-platform`), completing the first-run wizard, deploying
Stage 2 (`02-nerdio-config`), or running post-deployment verification.

## Workflow

1. **Stage 1 (`01-platform`)**:
   - Local/Cloud Shell: `./nerdio plan --stage platform` then `./nerdio apply --stage platform`.
   - Gated Pipeline: Trigger `.github/workflows/deploy.yml` with `stage=platform`, review the plan summary, and approve `<env>-apply`.
2. **AD DS Hybrid Storage Join (only when `identity_model = "ad_ds"`)**:
   - Run `ansible-playbook ansible/playbooks/ad-ds-fslogix-join.yml` from a domain-joined management host to join the FSLogix Azure Files storage account to Active Directory via `AzFilesHybrid`.
3. **First-Run Wizard & REST API**:
   - Complete the directory profile and first-run wizard in Nerdio Manager (or use `scripts/playwright/wizard-complete.spec.ts`), and confirm the REST API client is enabled.
4. **Stage 2 (`02-nerdio-config`)**:
   - Local/Cloud Shell: `./nerdio plan --stage config` then `./nerdio apply --stage config`.
   - Gated Pipeline: Trigger `.github/workflows/deploy.yml` with `stage=config`.
5. **Post-Wizard Verification**:
   - Run `./nerdio preflight --stage post-wizard --features all` (or pipeline `stage=verify`).
