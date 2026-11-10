---
status: proposed
date: 2026-11-10
decision-makers: [maintainers]
---

# 0035. Rename the repository to nme-automation, in place, keeping GitHub's redirect

## Context and Problem Statement

The repository was named for its first tool (HCL), but it now also carries a Bicep variant, a setup
chatbot, a readiness preflight and CI/CD for Nerdio Manager for Enterprise (NME). The owner wants it
called `nme-automation`. A GitHub rename redirects web, git and API traffic from the old
name, but some things embed the repository name and do not follow a redirect: GitHub OIDC token
subjects that Azure federated credentials match, container image names, settings saved in the
deployed chat, and signed release attestations. How is it renamed without breaking a deployment,
and what happens to the old name?

## Considered Options

- Rename in place in GitHub settings and rely on the redirect; no repository is created at the old name
- Rename in place, then create an archived stub repository at the old name that points to the new one
- Create a new repository, push the history to it, and archive the old one as a stub

## Decision Outcome

Chosen option: "Rename in place and rely on the redirect", because it keeps issues, pull requests,
stars, releases, environments, secrets and rulesets, and the redirect keeps every old link and
clone working. A stub at the old name would break that redirect (GitHub drops it as soon as a
repository with the old name exists), so a stub is the fallback only if the rename can't be done in
place or the redirect is later lost.

The repository's text moves to the new name in one pull request merged right after the rename. The
old name stays only in accepted decision records (history), in legacy fallbacks that keep profiles
and Cloud Shell clones made before the rename working, and as the family key in `family.yaml` so
sibling knowledge bases still match it. `scripts/nerdio/test_repo_name.py` fails on any other use.

### Consequences

- Good, because nothing a user cloned, bookmarked or linked breaks, and no history moves.
- Good, because the guard test catches the old name in work merged later from older branches.
- Bad, because Azure federated credentials for GitHub Actions (deploy pipeline, Key Vault and
  OpenBao hand-off) match `repo:<owner>/<name>:...` and must be re-applied with the new name before
  the next pipeline run, and the deployed chat needs its repository settings re-applied.
- Bad, because the chat's container image gets a new name and is only published after the first
  build on `main` following the rename.
- Neutral, because the old name must never be reused for another repository while the redirect is wanted.

## More Information

The step-by-step order (open pull requests, the rename, re-applies, the project's repository
setting) is in the pull request that adopts this decision.
