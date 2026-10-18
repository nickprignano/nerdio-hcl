---
title: "Keeping the knowledge base current"
summary: "How the KB stays current: the weekly source digest, the prior-art check, the feedback loop and the freshness check"
topic: curation
status: verified
last_reviewed: 2026-10-16
---

# Keeping the knowledge base current

Four tools keep the KB current without spending time (or LLM tokens) rediscovering things. Two
bring new information in (the weekly digest and the prior-art check), and two check that what's
already here still holds (the feedback loop and the monthly freshness check).

## Weekly digest (`kb-curator`)

[`.github/workflows/kb-curator.yml`](../../.github/workflows/kb-curator.yml) runs every Monday.
It reads [sources.toml](sources.toml), collects anything new from the last 8 days and opens an
issue labelled **kb-digest** with a checklist. Items whose URL is already linked from the KB are
left out. If nothing is new, no issue is opened.

Watched today:

- Nerdio's Terraform provider (commits, releases, issues and PRs, and its OpenAPI spec on its own),
  Nerdio's NMW repo (Marketplace template and runbooks), the Get-Nerdio GitHub org and the Nerdio
  help center
- azurerm (filtered to resources the kit uses), azuread, Terraform, Packer and the Packer Azure plugin
- The Windows Desktop Optimization Tool (WDOT, VDOT's successor) and Azure updates about AVD, FSLogix and Azure Files
- Community experts and official channels, through their blogs, YouTube channels and GitHub
  accounts, chosen and scored with the method in [experts.md](experts.md). X isn't watched,
  because it has no free feed. Busy sources are filtered to Nerdio and AVD topics
- New GitHub repos matching "nerdio terraform", "nerdio packer" and AVD + Packer + Terraform

Working a digest: for each ticked item, add what matters to the page named next to the source
(facts, versions, fixes; not a link dump), then close the issue.

To watch something else, add a `[[source]]` table to [sources.toml](sources.toml). Supported
kinds: `github_releases`, `github_commits` (optionally limited to one `path`), `github_issues`,
`github_org_repos`, `github_user_repos`, `github_search`, `feed`
(RSS/Atom, with optional `keywords`) and `zendesk`. Run it locally with:

```bash
GITHUB_TOKEN=$(gh auth token) python3 scripts/kb/curate.py --since-days 30
```

A source that fails (rate limit, site down) is listed at the bottom of the digest and doesn't
stop the others.

## Prior-art check (`kb-prior-art`)

Before building something new, check whether it's already solved:

```bash
GITHUB_TOKEN=$(gh auth token) python3 scripts/kb/prior_art.py "nerdio host pool"
```

or run **Actions > kb-prior-art** with the topic. It searches, in order: this KB, GitHub
repositories, Terraform/HCL code, and issues and pull requests. If something useful turns up,
record it in [nerdio/community-projects.md](nerdio/community-projects.md) or the relevant topic
page, so the next person doesn't search again.

The digest and prior-art scripts use only the Python standard library (3.11+).

## Tracking X accounts (option, not enabled)

Some community voices post mostly on X. The digest doesn't watch X today: blogs, YouTube and GitHub
cover the same people for free, which fits [decision 0009](decisions/0009-prefer-azure-github-hashicorp-oss.md).
If X-only posts turn out to matter, there are two paid routes. Both were checked against the
vendors' own docs on 2026-10-16; prices change often, so re-check before using either.

- **X API:** [pay-per-usage](https://docs.x.com/x-api/getting-started/pricing) with prepaid
  credits and no subscription. The pricing page doesn't mention the older Free, Basic or Pro
  tiers. A post read costs $0.005 and a user read $0.010, charged per resource returned. Reading
  your own account's posts is $0.001. Repeat reads of the same resource within a UTC day aren't
  charged again, the cap is 3 million post reads a month, and you can set a spending limit.
- **xAI Grok API:** the [X Search tool](https://docs.x.ai/developers/tools/x-search) (`x_search`,
  in the Responses API) searches X posts and can be limited to up to 20 handles
  (`allowed_x_handles`) and a date range (`from_date`, `to_date`). It [costs](https://docs.x.ai/developers/pricing)
  $5 per 1,000 posts and $10 per 1,000 profiles returned, plus model tokens (about $1.25 per
  million input tokens for general-purpose models). The model can also summarise the posts in the
  same call.

**Rough cost** for the roughly ten accounts in the weekly digest, at about five posts each per week:
around $1 a month either way. That's cheap, but it adds a third-party account and API key. Under
0009 that needs a decision record saying why blogs, YouTube and GitHub fell short. The X API is
the simpler fit because it returns raw posts that the deterministic curator can filter. The Grok
route adds an AI step to a pipeline that otherwise uses no LLM.

## Knowledge base family

This kit, AI (the hub for how the family uses AI) and AVD keep knowledge bases in this format. [family.yaml](family.yaml) lists them, what each one is the source of
truth for, and the format version each follows. `build.py` turns it into the "Related knowledge
bases" table in the [README](README.md#related-knowledge-bases) and a section in `llms.txt`.

- **Watch each other:** once a sibling's repo is in `family.yaml`, add two `github_commits`
  sources for it here, one with `path = "docs/knowledge/decisions"` and one with
  `path = "docs/knowledge"`, both pointing at this page. A private sibling repo may not be
  readable with the built-in token; keep the sources anyway.
- **Checked, not just agreed:** `validate.py` fails if a sibling with a repo in `family.yaml` is
  missing either source. The monthly freshness check (`--family`) reads each sibling's own
  `family.yaml` and flags one on a different `format_version`, one it can't read, and one whose
  repo isn't linked yet. The prior-art check searches each linked sibling's KB before GitHub.
- **Link, don't copy:** a fact that belongs to a sibling's topic is linked, not duplicated. If we
  learn something a sibling needs, open an issue or PR on their repo with the evidence.
- **Shared format:** schemas, scripts, checks, workflows and guardrails stay the same across the family.
  A change to them is proposed as a "Family format" decision, made in each KB, and the
  `format_version` is bumped everywhere once all have merged.
- **AI knowledge:** general findings about the Claude API, Foundry, model choice, keyless sign-in
  for AI APIs, prompts and evaluations go to the AI hub. Decisions about how this kit uses AI stay
  here and link to it.

## Feedback loop (`kb-feedback`)

Real results flow back into the KB through two issue forms:

- **Knowledge base feedback:** what worked, broke, went out of date or is missing, for one page.
  Use it after a sandbox run, a CI failure caused by stale advice, or any time the KB was wrong.
- **Known error:** an error, its cause and fix, for the [troubleshooting catalog](troubleshooting/README.md).

A maintainer reviews the issue and, if it's useful and public-safe, labels it **kb-accepted**.
[`.github/workflows/kb-feedback.yml`](../../.github/workflows/kb-feedback.yml) then appends it to
[field-reports.yaml](field-reports.yaml) or [known-errors.yaml](troubleshooting/known-errors.yaml),
regenerates and validates the KB, and opens a pull request that closes the issue. If the form is
incomplete or fails validation, the workflow comments on the issue instead.

The label is the safety gate: issue text from anyone is only parsed as data, the PR still goes
through review, and gitleaks and the KB checks run on it. Two repository settings matter. The
[pipeline bootstrap](../pipeline.md#set-it-up-once-in-cloud-shell) sets both in Terraform
(`modules/github-repo`); if you don't use the pipeline:

- Run **Actions > kb-freshness** once so the `kb-*` labels exist (issue forms only apply labels
  that already exist).
- Allow GitHub Actions to create and approve pull requests:
  `gh api -X PUT repos/{owner}/{repo}/actions/permissions/workflow -f default_workflow_permissions=read -F can_approve_pull_request_reviews=true`.
  Without it, the workflow pushes the branch and asks you to open the PR.

Pull requests opened by the workflow's own token don't start other workflows. The job runs the KB
checks itself; close and reopen the PR to run the full CI before merging.

## Freshness check (`kb-freshness`)

[`.github/workflows/kb-freshness.yml`](../../.github/workflows/kb-freshness.yml) runs on the 1st
of each month and keeps one open issue labelled **kb-freshness** listing:

- pages reported broken or outdated in field reports that aren't marked `resolved` yet
- pages whose `last_reviewed` is more than 90 days old (pages with status `plan` are skipped)
- pages with status `unverified` or `partial`, with the number of claims still marked *unverified*
- known errors whose fix is still unverified

Work it by re-checking each item against a primary source or a real run, then updating the page's
text, `last_reviewed` and `status`. Run it locally with `python3 scripts/kb/freshness.py`.

## Checks on every change (`kb-validate`)

[`.github/workflows/kb-validate.yml`](../../.github/workflows/kb-validate.yml) runs on pull
requests that touch the KB. It runs `validate.py` (front matter and YAML against the
[schemas](schema/page.schema.json), MADR sections, links and anchors, email and public-IP
patterns), checks the generated tables and `llms.txt` are up to date (`build.py --check`), and
runs the KB scripts' unit tests. Secrets are caught by gitleaks in the main `validate` workflow.
