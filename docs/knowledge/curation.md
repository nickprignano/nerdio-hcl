# Keeping the knowledge base current

Two tools keep the KB fed without spending time (or LLM tokens) rediscovering things.

## Weekly digest (`kb-curator`)

[`.github/workflows/kb-curator.yml`](../../.github/workflows/kb-curator.yml) runs every Monday.
It reads [sources.toml](sources.toml), collects anything new from the last 8 days and opens an
issue labelled **kb-digest** with a checklist. Items whose URL is already linked from the KB are
left out. If nothing is new, no issue is opened.

Watched today:

- Nerdio's Terraform provider (commits and releases), the Get-Nerdio GitHub org and the Nerdio
  help center
- azurerm (filtered to resources the kit uses), azuread, Terraform, Packer and the Packer Azure plugin
- The Virtual Desktop Optimization Tool and Azure updates about AVD, FSLogix and Azure Files
- New GitHub repos matching "nerdio terraform", "nerdio packer" and AVD + Packer + Terraform

Working a digest: for each ticked item, add what matters to the page named next to the source
(facts, versions, fixes; not a link dump), then close the issue.

To watch something else, add a `[[source]]` table to [sources.toml](sources.toml). Supported
kinds: `github_releases`, `github_commits`, `github_org_repos`, `github_search`, `feed`
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

Both scripts use only the Python standard library (3.11+).

_Last reviewed: 2026-10-16_
