---
name: handover
description: Generate a sanitized, customer-ready operational handover runbook from the environment's answers and readiness report.
---

# Handover Skill (`nerdio-hcl`)

Use this skill after Stage 1, Stage 2, and `--stage post-wizard` verification complete to produce an
operational handover guide for the customer's AVD administration team.

## Contents to Generate

1. **Architecture Summary**:
   - Cloud environment (`public` or `usgovernment`), region (`location`), and identity model (`entra_joined`, `entra_ds`, or `ad_ds`).
   - Secret store (`key_vault` or `openbao`) and network hardening posture (`enable_hardening`).
2. **Day-2 Operations**:
   - How to update host pool capacity, VM SKUs, and auto-scale schedules via `schema/parameters.json` and `.github/workflows/deploy.yml`.
   - How to rebuild the monthly golden image via `.github/workflows/image.yml`.
   - For static or personal host pools, how to run `ansible/playbooks/session-host-day2.yml` with the Azure RM dynamic inventory (`ansible/inventory/azure_rm.yml`).
   - Certificate renewal checks (`nme.keyvault`, `nme.automation`, `nme.entra_app`) via `./nerdio preflight --stage post-wizard`.
