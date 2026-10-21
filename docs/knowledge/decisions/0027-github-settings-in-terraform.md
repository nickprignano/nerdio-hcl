---
status: proposed
date: 2026-10-21
decision-makers: [maintainers]
---

# 0027. The repository's own GitHub settings are Terraform with no saved state, planned daily and applied only by the owner

## Context and Problem Statement

The repository's GitHub settings (the ruleset on `main`, merge and auto-merge, required checks,
labels, push protection, Dependabot, topics) were clicked in by hand or left to the deploy
bootstrap, which never ran against this repository: `main` had no ruleset at all. The deploy
pipeline's apply environment trusts `main`, and the owner's GitHub work conventions (ai-brain 0014)
need a ruleset and required checks to be safe. How do the settings stay declared, reviewed and
free of drift, without a long-lived credential and without anything applying on its own?

## Considered Options

- Safe Settings (a hosted GitHub App that applies YAML settings from an admin repository)
- OpenTofu with the same provider
- Terraform with a saved state in Azure storage or HCP Terraform
- Terraform with no saved state: every run imports what exists

## Decision Outcome

Chosen option: "Terraform with no saved state", because the kit already runs Terraform everywhere
(including Cloud Shell), a plan that imports first always compares the code with GitHub itself,
and there's no state store that the owner's other repositories would also need.

- `github/` is its own root, separate from the deploy stages. `modules/github-settings` holds the
  settings; its defaults are ai-brain 0014's conventions plus push protection (ai-brain 0016) and
  Dependabot. Required checks are pinned to GitHub Actions.
- A daily workflow plans with a read-only GitHub App whose key is an environment secret limited to
  `main`, and keeps one `settings-drift` issue. It has no apply step and its token can't write.
- The owner applies from Cloud Shell with a fine-grained token for this repository only, valid for
  one day, typed in hidden and revoked afterwards.
- The deploy bootstrap no longer manages repository settings; it warns while `main` has no ruleset.

### Consequences

- Good, because drift is visible every day and nothing changes on GitHub without the owner.
- Good, because CI never holds a credential that can change settings.
- Bad, because the read key's environment has no required reviewer, which ai-brain 0016 asks for
  on environment secrets: a scheduled job can't wait for a click. The key can only read settings
  of one repository.
- Bad, because each apply needs a hand-made token, and a fork of the kit has to set up its own App
  to get the drift check.

## More Information

Spec and red-team review (Fable, 2026-10-21; thirteen findings folded in) in the project's
scoping notes. Safe Settings is built for organizations and applies on its own, the opposite of
the ask; OpenTofu would run the same code but isn't in Cloud Shell. Revisit if GitHub offers OIDC
sign-in to its own API, or when ai-brain takes the module into its template.
