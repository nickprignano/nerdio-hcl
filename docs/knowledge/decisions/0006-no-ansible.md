# 0006. No Ansible

- **Status:** Accepted
- **Date:** 2026-10-16

## Context

Ansible could configure session hosts (it can find Nerdio-built hosts through the `azure_rm`
inventory by tag) or replace the Packer PowerShell scripts. But Nerdio auto-scale keeps creating
and destroying hosts, so anything configured after deployment drifts, and Nerdio already has
scripted actions, schedules and auto-scale for runtime work.

## Decision

The kit doesn't use Ansible. Terraform owns desired state; Nerdio's auto-scale, schedules and
scripted actions (managed with `nme_scripted_action`) own runtime work. Gaps in `nerdio/nme`
are filled with REST API calls from workflows for now, and Terraform actions in the provider
later (see [../nerdio/upstream-contributions.md](../nerdio/upstream-contributions.md)).

## Consequences

- One fewer tool for community users to learn and run.
- Image-time configuration stays in Packer's PowerShell provisioners.
