---
status: rejected
date: 2026-10-18
decision-makers: [maintainers]
---

# 0023. The AI hub owns the family's KB format, and this kit follows it as a member

## Context and Problem Statement

[0021](0021-knowledge-base-family.md) made this kit the reference implementation of the shared
KB format, so every format change had to start here. A later proposal suggested moving format
ownership to `ai-brain` as an upstream hub. Should `nerdio-hcl` defer its KB format and topic
ownership to `ai-brain` / `avd-second-brain`, or stay self-contained ("aware but separate")?

## Considered Options

- Keep this kit self-contained, owning its own KB format and topics while staying read-only aware of sibling repos
- Make the AI hub the format's source of truth, with this kit as a member

## Decision Outcome

Rejected "The AI hub owns the format". Chosen option: "Keep this kit self-contained (aware but
separate)", because `nerdio-hcl` is a standalone deployment kit whose knowledge base must be
grounded directly in primary Nerdio, Microsoft (AVD, FSLogix, Entra), HashiCorp and community
expert sources without depending on external personal repos as an upstream source of truth.

- This repository owns its own KB schemas (`docs/knowledge/schema/`), scripts (`scripts/kb/`),
  workflows and topics.
- Sibling repositories listed in [family.yaml](../family.yaml) (`ai-brain`, `avd-second-brain`)
  are peers that this repo is **aware of, not governed by**: the curator and prior-art check can
  watch their KBs read-only for awareness, but `nerdio-hcl` maintains its own verified facts and
  format independently.
