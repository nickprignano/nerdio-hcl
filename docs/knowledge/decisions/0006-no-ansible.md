---
status: accepted
date: 2026-10-16
decision-makers: [maintainers]
---

# 0006. No Ansible

## Context and Problem Statement

Ansible could configure session hosts (it can find Nerdio-built hosts through the `azure_rm`
inventory by tag) or replace the Packer PowerShell scripts. But Nerdio auto-scale keeps creating
and destroying hosts, so anything configured after deployment drifts. Does the kit need Ansible?

## Considered Options

- No Ansible: Terraform owns desired state, Nerdio owns runtime work
- Ansible for post-deployment host configuration

## Decision Outcome

Chosen option: "No Ansible", because Nerdio already has scripted actions, schedules and
auto-scale for runtime work. Terraform owns desired state; Nerdio's auto-scale, schedules and
scripted actions (managed with `nme_scripted_action`) own runtime work. Gaps in `nerdio/nme` are
filled with REST API calls from workflows for now, and Terraform actions in the provider later
(see [../nerdio/upstream-contributions.md](../nerdio/upstream-contributions.md)).

### Consequences

- Good, because there's one fewer tool for community users to learn and run.
- Neutral, because image-time configuration stays in Packer's PowerShell provisioners.
