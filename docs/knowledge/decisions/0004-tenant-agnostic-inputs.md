---
status: accepted
date: 2026-10-16
decision-makers: [maintainers]
---

# 0004. Tenant and subscription are inputs, never hardcoded

## Context and Problem Statement

The kit is developed against a sandbox tenant and is meant to be shared publicly and reused in
other tenants. Where do environment-specific values live?

## Considered Options

- Everything environment-specific is a variable; the repo holds only a placeholder example
- Commit per-environment tfvars to the repo

## Decision Outcome

Chosen option: "Everything is a variable", because the repo will be public. Tenant ID,
subscription ID, names, regions and address ranges are variables. The repo only holds an
`example` environment with placeholder values; real environments copy it and keep their tfvars
and state out of git. Docs follow the same rule (see the public-safe checklist in
[../README.md](../README.md#keep-it-public-safe)).

### Consequences

- Good, because anyone can use the kit by copying the example environment.
- Good, because nothing in the repo identifies the environments it was tested in.
