# This repository's GitHub settings

`github/` declares this repository's own GitHub settings in Terraform, so a difference between
GitHub and the code shows up in `terraform plan`: the ruleset on `main`, merge and auto-merge
settings, required checks, the labels the workflows use, push protection and Dependabot, and
topics. The settings come from [`modules/github-settings`](../modules/github-settings), whose
defaults are the owner's GitHub work conventions; [`main.tf`](main.tf) holds only this repository's
own values. [Decision 0027](../docs/knowledge/decisions/0027-github-settings-in-terraform.md) says
why.

It's separate from the deploy stages, with its own state, and it never touches Azure.

## No saved state

There's no backend. Every run starts empty and imports what exists ([`imports.tf`](imports.tf)),
so a plan always compares the code with GitHub itself:

- `import`, no change: GitHub matches the code
- `update`: GitHub differs (drift, or a change you made in the code)
- `create`: something the code declares doesn't exist yet

So there's no state file to store, lock or protect. `settings.sh` deletes the local one before and
after each run.

## Plan or apply, from Cloud Shell

```bash
./github/settings.sh          # plan only: what would change on GitHub
./github/settings.sh apply    # plan, then apply after you type yes
```

It asks for a token without showing it. Create one for each apply and revoke it afterwards
(GitHub, Settings, Developer settings, Fine-grained tokens):

| | |
|---|---|
| Repository access | Only this repository |
| Expiration | One day |
| Repository permissions | Administration: read and write; Issues: read and write; Metadata: read |

A plan alone works with the same token, or one with only read permissions.

## The daily drift check

[`github-settings-drift.yml`](../.github/workflows/github-settings-drift.yml) plans every day
with a read-only GitHub App and keeps one `settings-drift` issue open while GitHub and the code
differ; it closes the issue when they match again. It never applies. To fix drift, either change
the code to match GitHub in a pull request, or apply the code with `settings.sh apply`.

Set it up once:

1. Create a GitHub App owned by your account: webhook off; repository permissions
   Administration: read, Issues: read, Metadata: read; installable only on this account.
   Generate a private key.
2. Install the App on this repository only.
3. Keep the key in your password manager, noting where it's deployed, and delete the download.
4. Create the environment `github-settings-read` with deployment branches limited to `main`.
   Add the App's ID as the variable `SETTINGS_APP_ID` and the key's text as the secret
   `SETTINGS_APP_KEY`.
5. Run the workflow once by hand (Actions, github-settings-drift, Run workflow).

Every right involved is listed in [docs/access.md](../docs/access.md).

## Another repository

Copy `github/` and change `main.tf`: description, topics, the jobs that run on every pull
request (a required check that never reports holds every pull request) and labels. Keep the
module's defaults unless you mean to differ from the conventions.
