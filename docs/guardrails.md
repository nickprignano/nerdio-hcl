# Guardrails

The rules every change to this kit follows, whoever makes it: a person, a pipeline or an AI
assistant. They exist so the kit can be public, automated and safe at the same time. CI enforces
the ones it can (marked **CI**). Reviewers check the rest.

## 1. Automate, but never at the expense of security

The goal is a turnkey deployment (copy-paste, one button or chat). Automation never weakens a
control to save a step: no shared admin passwords, no long-lived secrets where an identity or a
certificate works, no broader roles than the job needs. When something can't be automated safely,
the kit documents the manual step and the workaround instead
([decision 0011](knowledge/decisions/0011-terraform-native-install.md)).

## 2. HCL first; scripts are thin glue

If Terraform (or Packer) can do it, it's done in HCL. A script is allowed only as a minimal
bootstrap (installing Terraform, writing gitignored tfvars) or as a stopgap until Terraform can
take over, and it says so in its header. Never add a script for something Terraform already does.

## 3. Works from a browser: Cloud Shell on an iPad

Every step must run in Azure Cloud Shell (Bash) from a browser, on a tablet included. No local
installs and no desktop-only tools. IDs come from `az account show`, never typed in
([decision 0012](knowledge/decisions/0012-cloud-shell-baseline.md)).

## 4. Nothing public identifies a real environment (**CI**: gitleaks, tracked-file check)

The repo and its knowledge base are public. Never commit:

- tenant, subscription, object, client or resource IDs from a real tenant
- domains, UPNs, emails, hostnames, real IP ranges
- secrets, keys, SAS tokens, connection strings, state or plan files
- employer, customer or tenant names

Real values live only in gitignored files (`*.tfvars`, `*.auto.tfvars.json`, `*.pkrvars.hcl`)
or in the pipeline's secret store. Examples use `contoso` names, all-zero GUIDs and `10.x`
ranges. Published Microsoft or Nerdio identifiers (the same in every tenant) are fine.

## 5. Secrets never pass through chat or files in the repo

Secrets come from Key Vault (later Vault), OIDC federation or environment variables, and are
marked `sensitive` in Terraform. Scripts never print IDs or secrets. A chat assistant never asks
for, shows or stores a secret; the user runs the step that handles it.

## 6. Every change through a PR; nothing applies without a yes

Changes land through pull requests with green CI. `terraform apply` runs only when the person who
owns the tenant runs it (Cloud Shell asks them to type `yes`) or approves the pipeline
environment. Plan first, always. An assistant prepares the change; it never applies it.

## 7. Respect licenses: unlicensed code is reference only

- [Get-Nerdio](https://github.com/Get-Nerdio) repositories, including the `nerdio/nme` provider,
  and [MB-External/NME-Terraform](https://github.com/MB-External/NME-Terraform) have **no license**.
  Use them for facts (setting names, API calls, behavior). Never copy, adapt, fork, re-host or
  redistribute their code or binaries.
- The kit downloads `nerdio/nme` from Nerdio's own GitHub release at install time
  (`scripts/install-nme-provider.sh`) and never vendors it.
- Nerdio's app package is fetched from Nerdio's service at install time and never stored here.
- Record where a fact came from (repo and commit) in the [knowledge base](knowledge/README.md)
  ([decision 0013](knowledge/decisions/0013-unlicensed-code-reference-only.md)).

## 8. Ask Nerdio before working around Nerdio

When only Nerdio can fix a gap (an API, a license, a supported install path), the kit uses the
safest workaround it can and records the ask, with evidence, in
[upstream-contributions.md](knowledge/nerdio/upstream-contributions.md). Nothing is sent to Nerdio
without the maintainer's go-ahead. Scripted UI sessions against the Nerdio console stay unpublished
until Nerdio says they're allowed.

## When a guardrail gets in the way

Don't work around it quietly. Open an issue or a decision record that says which guardrail, why,
and what the safer alternative is. A guardrail changes only by a new decision record.
_Last reviewed: 2026-10-16_
