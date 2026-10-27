---
status: accepted
date: 2026-10-18
decision-makers: [maintainers]
---

# 0021. This KB is aware of sibling knowledge bases, while staying separate and self-contained

## Context and Problem Statement

The maintainer runs several separate repositories that each keep a knowledge base (`nerdio-hcl`,
`avd-second-brain`, and `ai-brain`). Should they be merged or governed by one central repo, or kept
separate with read-only awareness?

## Considered Options

- Completely isolated knowledge bases with no awareness of each other
- One shared or centrally governed knowledge base
- Separate, self-contained knowledge bases that share a compatible format and stay read-only aware of each other ("aware but separate")

## Decision Outcome

Chosen option: "Aware but separate", because `nerdio-hcl` must work as a standalone kit with its
own knowledge base grounded directly in Nerdio, Microsoft (AVD, FSLogix, Entra), HashiCorp and the
tracked expert community ([sources.toml](../sources.toml), [experts.yaml](../experts.yaml)), while
still allowing the weekly digest and prior-art check to notice relevant work in sibling repos.

- **Self-contained source of truth:** This KB owns its own format, schemas, scripts and topics
  (Nerdio Manager, `nerdio/nme`, AVD and FSLogix for this kit, Terraform, Packer, and the kit's
  setup chatbot). Primary sources are official Nerdio, Microsoft and HashiCorp documentation/repos
  plus the scored community experts in [experts.yaml](../experts.yaml).
- **Aware, not coupled:** [family.yaml](../family.yaml) lists sibling repositories (`ai-brain`,
  `avd-second-brain`) so `scripts/kb/curate.py` and `scripts/kb/prior_art.py` can watch them
  read-only. No content or project work is automatically copied between repos, and this repo never
  defers its source of truth to a sibling repo ([0023](0023-ai-brain-is-the-family-format-source.md)).

### Consequences

- Good, because `nerdio-hcl` and its KB stand completely on their own for any user or contributor.
- Good, because the maintainer still gets digest and prior-art visibility across sibling repos.
- Neutral, because private sibling repos are simply skipped when read with the default workflow token.
