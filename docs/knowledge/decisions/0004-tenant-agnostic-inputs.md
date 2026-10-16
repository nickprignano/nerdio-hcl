# 0004. Tenant and subscription are inputs, never hardcoded

- **Status:** Accepted
- **Date:** 2026-10-16

## Context

The kit is developed against a sandbox tenant and is meant to be shared publicly and reused in
other tenants.

## Decision

Tenant ID, subscription ID, names, regions and address ranges are variables. The repo only holds
an `example` environment with placeholder values; real environments copy it and keep their
tfvars and state out of git. Docs follow the same rule (see the public-safe checklist in
[../README.md](../README.md#keep-it-public-safe)).

## Consequences

- Anyone can use the kit by copying the example environment.
- Nothing in the repo identifies the environments it was tested in.
