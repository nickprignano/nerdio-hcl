---
title: "Knowledge base"
summary: "What this knowledge base is, how it's organised, and how to add to it safely"
topic: overview
status: verified
last_reviewed: 2026-10-16
---

# Knowledge base

What we've learned building a HashiCorp-stack (Terraform + Packer) deployment kit for
**Nerdio Manager for Enterprise** on Azure Virtual Desktop. It covers research findings, gotchas
and the decisions behind the kit, and it is meant to be read and added to by anyone using the kit.

The kit's goal: automate everything that can and should be automated, behind a turnkey
copy-paste, button or chat experience, so a community user does as little heavy lifting as
possible ([roadmap](stack-options.md)).

This is a living document set. When something new is learned, add it to the topic page it
belongs to instead of starting a new file.

## Index

<!-- BEGIN GENERATED: kb-index (from front matter; run scripts/kb/build.py) -->
| Page | What's in it | Status |
|---|---|---|
| [workbenches.md](workbenches.md) | Where to run the kit from a browser: Azure Cloud Shell (baseline) or GitHub Codespaces (optional), with their limits | partial |
| [nerdio/ai-features.md](nerdio/ai-features.md) | Copilot, ScriptPro, AnalyticsPro and the MCP connector: what they run on, and how they relate to the kit's setup chat | partial |
| [nerdio/avd-hybrid.md](nerdio/avd-hybrid.md) | Azure Virtual Desktop Hybrid (on-premises session hosts via Azure Arc): support status, what Nerdio Manager adds on Nutanix AHV, and the minimum viable lab kit and hardware to test it | partial |
| [nerdio/community-projects.md](nerdio/community-projects.md) | Other Nerdio + Terraform projects worth knowing about | verified |
| [nerdio/entra-app.md](nerdio/entra-app.md) | The nerdio-nmw-app registration, permissions, app roles and the REST API client | partial |
| [nerdio/platform.md](nerdio/platform.md) | What the Marketplace deployment creates, the install step, setup wizard, roles and hardening | partial |
| [nerdio/readiness.md](nerdio/readiness.md) | The read-only readiness engine behind ./nerdio preflight: stages, statuses, rights, and how it sits beside Nerdio's own readiness script | partial |
| [nerdio/terraform-provider.md](nerdio/terraform-provider.md) | Nerdio's own nerdio/nme provider: auth, resources, coverage gaps, how to build it | verified |
| [nerdio/upstream-contributions.md](nerdio/upstream-contributions.md) | Gaps, API asks and doc fixes we could raise with Nerdio, with evidence | partial |
| [terraform/azurerm-5.md](terraform/azurerm-5.md) | azurerm 5.x and azuread 3.x changes we hit, with fixes | partial |
| [terraform/github-settings.md](terraform/github-settings.md) | Declaring a repository's own GitHub settings with integrations/github, imported on every run, with a read-only drift check | unverified |
| [terraform/restricted-networks.md](terraform/restricted-networks.md) | Running Terraform and Packer where the registry is blocked | verified |
| [terraform/testing-and-ci.md](terraform/testing-and-ci.md) | terraform test, tflint, the CI workflow and planned post-deploy checks | verified |
| [packer/avd-image.md](packer/avd-image.md) | Building a Windows 11 multi-session image for Nerdio with Packer | partial |
| [security/](security/README.md) | Security baselines Nerdio publishes, kit hardening, and how to record accepted risks | partial |
| [troubleshooting/](troubleshooting/README.md) | Known errors: symptom, cause, fix and source | verified |
| [chat-assistant.md](chat-assistant.md) | What the chat assistant covers across the lifecycle: planning, security review, readiness, troubleshooting and day 2 | plan |
| [chatbot-first.md](chatbot-first.md) | Every deployment step, whether the setup chat can drive it today, what blocks it, and the automation fix or workaround | plan |
| [stack-options.md](stack-options.md) | Roadmap to a turnkey, maximum-automation deployment: the experience, which manual steps can go, which tools fit, and what Nerdio would need to change | plan |
| [curation.md](curation.md) | How the KB stays current: the weekly source digest, the prior-art check, the feedback loop and the freshness check | verified |
| [experts.md](experts.md) | How we choose which Nerdio and AVD experts the KB follows: the study method, the scores, and the published list | verified |
| [decisions/](decisions/README.md) | Decision records (MADR): what was decided and why |  |
<!-- END GENERATED: kb-index -->

## Related knowledge bases

This KB is self-contained and owns its own format, schemas, scripts and topics, grounded directly
in primary Nerdio, Microsoft (AVD, FSLogix, Entra), HashiCorp and tracked community expert sources
([sources.toml](sources.toml), [experts.md](experts.md)). It stays **aware but separate** from the
sibling knowledge bases listed in [family.yaml](family.yaml) ([decision 0021](decisions/0021-knowledge-base-family.md),
[0023](decisions/0023-ai-brain-is-the-family-format-source.md)): they are watched read-only for
awareness in the digest and prior-art search, without deferring this kit's source of truth to them.
See [curation.md](curation.md#knowledge-base-family).

<!-- BEGIN GENERATED: family (from family.yaml; run scripts/kb/build.py) -->
| Knowledge base | Role | Focus | Source of truth for |
|---|---|---|---|
| [AI](https://github.com/nickprignano/ai-brain/tree/main/docs/knowledge) | member | Standalone AI research and experimentation (watched read-only for awareness) | General AI research; model evaluations and AI workflows |
| [AVD](https://github.com/nickprignano/avd-second-brain/tree/main/docs/knowledge) | member | Standalone Azure Virtual Desktop research (watched read-only for awareness) | Standalone Azure Virtual Desktop and EUC research |
<!-- END GENERATED: family -->

## Before you build something

Every change follows the project's [guardrails](../guardrails.md): security over convenience, HCL
first, the Cloud Shell baseline, no leaks, no secrets in chat, pull requests only, and license rules.

Run the prior-art check first (`python3 scripts/kb/prior_art.py "<topic>"`, see
[curation.md](curation.md#prior-art-check-kb-prior-art)). It searches this KB and GitHub, so
you don't spend time on problems someone has already solved.

## How to add to it

Two ways in, both reviewed before anything merges:

- **Without editing files:** open a **Knowledge base feedback** issue (what worked, broke, went
  out of date or is missing) or a **Known error** issue. When a maintainer labels it
  `kb-accepted`, a workflow turns it into a pull request. See [curation.md](curation.md#feedback-loop-kb-feedback).
- **With a pull request:**
  - **A fact or gotcha:** add a bullet to the matching topic page. Say what happened, the fix,
    and the versions it applies to. Mark anything you haven't confirmed as *unverified*.
  - **A known error or an upstream ask:** add an entry to
    [troubleshooting/known-errors.yaml](troubleshooting/known-errors.yaml) or
    [nerdio/upstream.yaml](nerdio/upstream.yaml), not to the Markdown table.
  - **A decision:** copy [decisions/template.md](decisions/template.md) to the next number. If a
    decision is reversed, write a new record and set the old one's status to `superseded by NNNN`.
  - **A new topic:** only when it doesn't fit an existing page. Give it front matter like the
    other pages; the index above picks it up.
  - When you change or re-check a page, update `last_reviewed` in its front matter, and `status`
    if it changed.
  - Run `python3 scripts/kb/build.py` and `python3 scripts/kb/validate.py` before pushing (see
    [Format](#format) for setup). CI runs both.

## Format

The KB uses open, common formats so people, tools and LLM agents can all read it:

- **Page front matter (YAML)** on every page: `title`, `summary`, `topic`, `status`
  (`verified`, `partial`, `unverified` or `plan`) and `last_reviewed`, validated against
  [schema/page.schema.json](schema/page.schema.json).
- **Decision records in [MADR](https://adr.github.io/madr/) format,** with `status` and `date` in
  front matter ([schema/decision.schema.json](schema/decision.schema.json)).
- **Structured YAML** for the [known errors](troubleshooting/known-errors.yaml),
  [upstream asks](nerdio/upstream.yaml) and [field reports](field-reports.yaml), each with a JSON
  Schema in [schema/](schema/page.schema.json). The Markdown tables are generated from them.
- **[`llms.txt`](../../llms.txt)** at the repo root, the [llms.txt](https://llmstxt.org) index that
  tells LLMs and agents what's here. It's generated too.

Generated parts sit between `BEGIN GENERATED` / `END GENERATED` comments; edit the source, not
the output. The scripts need Python 3.11+ with PyYAML and jsonschema, which works in Azure Cloud
Shell:

```bash
pip install --user -r scripts/kb/requirements.txt
python3 scripts/kb/build.py && python3 scripts/kb/validate.py
```

## Keep it public-safe

This repo is intended to be shared with the community, so nothing here may identify a real
environment. Before committing, check that your change has none of the following:

- Tenant IDs, subscription IDs, object or client IDs of your own apps, or resource IDs
- Domain names, UPNs, email addresses, internal hostnames or URLs
- IP ranges or CIDRs from a real network (use RFC 5737 / documentation ranges or `10.x` examples)
- Secrets, keys, SAS tokens, connection strings or state file excerpts
- Employer, customer or tenant names

Use placeholders such as `<tenant-id>`, `<subscription-id>`, `<app-name>` and `contoso.com`.
Write lessons as general advice ("in a sandbox tenant"), not as a story about a specific one.
Published Microsoft or Nerdio identifiers (for example the documented Nerdio app role IDs)
are fine, because they are the same in every tenant.
