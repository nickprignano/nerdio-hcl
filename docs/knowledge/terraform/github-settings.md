---
title: "GitHub settings in Terraform"
summary: "Declaring a repository's own GitHub settings with integrations/github, imported on every run, with a read-only drift check"
topic: terraform
status: verified
last_reviewed: 2026-10-28
---

# GitHub settings in Terraform

How `github/` and `modules/github-settings` work and what was learned building and verifying them
against this repository's live GitHub REST API ([decision 0027](../decisions/0027-github-settings-in-terraform.md)).

## No saved state

- Every run starts with an empty state and `import` blocks adopt what exists, so the plan compares
  code with GitHub: import with no change, update (drift) or create (missing).
- `import` blocks take `for_each` driven by data sources (Terraform 1.7+), read at plan time. Labels
  come from `data "github_issue_labels"`; the provider has no rulesets data source, so the ruleset
  is found by name through `data "github_rest_api"`, which uses the provider's own token.
- GitHub label names are case-insensitive: compare with `lower()` or an existing `No-KB` plans a
  create that fails with 422.
- Import IDs (integrations/github 6.13): repository `name`; label `repo:name`; ruleset `repo:id`
  (numeric); vulnerability alerts, Dependabot security updates and workflow permissions `repo`.

## Provider details that cause false drift

- `github_repository` always sends `is_template` (default false): ignore it, or a template repo
  gets un-templated.
- `security_and_analysis` is only read when the token can see it (admin, or Administration: read
  for an App); GitHub reports `advanced_security` on public repositories, so ignore that child.
- `vulnerability_alerts` on `github_repository` is deprecated in favour of
  `github_repository_vulnerability_alerts`; ignore the attribute when using the resource.
- `has_issues`, `has_wiki` and friends have no default: leave them unset and the plan turns them
  off. `github/` reads them from `data "github_repository"` so a fork keeps its own.

## Rulesets

- Bypass for the repository admin role: `actor_type = "RepositoryRole"`, `actor_id = 5`,
  `bypass_mode = "pull_request"` (PRs only, never a direct push).
- Pin required checks to GitHub Actions with `integration_id = 15368`, so a commit status from any
  other app can't satisfy them.
- A required check that never reports holds every PR: require only jobs with no `paths` filter.

## Tests and credentials

- `terraform test` can't import against a mock provider: add an `override_resource` for each
  imported resource, and `override_data` for the lookups.
- GitHub has no OIDC sign-in to its own API. The drift workflow uses a read-only GitHub App
  (`actions/create-github-app-token`, one-hour token); applies use a one-day fine-grained token.
  When `vars.SETTINGS_APP_ID` isn't configured in the `github-settings-read` environment yet,
  `github-settings-drift.yml` skips the token and plan steps cleanly instead of failing inside
  `@octokit/auth-app`. When drift is reported on a `settings-drift` issue, labeling the issue
  `kb-accepted` triggers `kb-feedback.yml` to open a pull request syncing `github/main.tf` (`merge`
  and `topics`) with the live repository.
- Anonymous REST calls from hosted runners share the 60-per-hour limit and fail at random; always
  send the token.

## Prior art

- [Safe Settings](https://github.com/github/safe-settings) (ISC): a hosted Probot app, settings in
  an organization's `admin` repo, applies and reverts drift itself. Built for organizations.
- OpenTofu runs the same code (import `for_each` from 1.7); not preinstalled in Cloud Shell.
