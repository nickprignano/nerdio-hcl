---
status: proposed
date: 2026-10-18
decision-makers: [maintainers]
---

# 0021. This KB is one of a family of knowledge bases, with the AI project as the hub for AI knowledge

## Context and Problem Statement

The maintainer runs several projects that each keep a second brain, among them this kit, AI
(the research behind them) and AVD. Several of them use AI the same way: the Claude API,
Microsoft Foundry, keyless sign-in, prompts. Without coordination they would drift apart in
format and copy each other's facts. How should they relate?

## Considered Options

- Independent knowledge bases
- One shared knowledge base for everything
- Knowledge bases that share one format, list each other and own separate topics, with the
  AI project as the hub for shared AI knowledge

## Decision Outcome

Chosen option: "Separate KBs, one format, separate ownership, AI as the hub", because each project
keeps its own reviewed KB next to its code while the family stays consistent and findable.

- [family.yaml](../family.yaml) lists the family, the topics each owns and the format version.
- Each KB watches the others' decisions and changes in its weekly digest, and links to a
  sibling's page instead of copying it.
- The format (schemas, scripts, checks, workflows, guardrails) changes only through a "Family
  format" decision made across the family. This kit is the reference implementation, at version 1.
- General AI knowledge (Claude API and Foundry use, model choices, keyless sign-in for AI APIs,
  prompts and evaluations) lives in the AI KB. How a project uses AI stays in that project, for
  example [0014](0014-self-hosted-setup-chatbot.md) and [0020](0020-claude-api-federation-for-the-chat.md)
  here.

### Consequences

- Good, because lessons learned once, such as keyless sign-in to the Claude API, are found by
  every project in the family.
- Good, because each project still works on its own, from its own repo.
- Bad, because a format change now takes one PR per KB.
- Neutral, because private sibling repos can't be watched with the built-in token until they're
  public.

## More Information

The setup prompt shared with the other projects is kept in the project files as
`prompts/kb-family-second-brain.md`. The sibling repo names are added to family.yaml once known.
