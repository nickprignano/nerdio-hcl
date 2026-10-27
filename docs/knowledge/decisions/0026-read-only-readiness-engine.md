---
status: accepted
date: 2026-10-19
decision-makers: [maintainers]
---

# 0026. Readiness checks are read-only, cover the whole lifecycle, and complement Nerdio's deployability test

## Context and Problem Statement

`./nerdio preflight` checked only the pre-install state, read the kit's own tfvars and hard-coded
the commercial cloud's endpoints. Nerdio's `Test-NmeDeploymentReadiness.ps1` answers a different
question, whether the installer's resources can be created, by creating them, which needs Owner
and has no license. People installing from the Marketplace, strict tenants and the pipeline's
read-only plan identity all need an answer before anything changes, and again after the install
and the wizard. How should the kit check readiness?

## Considered Options

- Extend `./nerdio preflight` only
- Wrap Nerdio's readiness script
- A standalone, read-only engine shared with the kit

## Decision Outcome

Chosen option: "A standalone, read-only engine shared with the kit", because it runs under
Reader in any tenant, before any change request exists, and the same checks serve every front door.

- One check registry (`scripts/nerdio/readiness/`) with stable IDs; each check states the right
  it needs, what it reads, its KB page and its source. CI fails a check that lacks one of those or
  that could write, and a guard refuses any `az` call that isn't a read.
- Stages (pre-install, post-install, post-wizard) and opt-in feature domains, so a first run isn't
  buried. Statuses include `no-access` and `skipped`, and a run that couldn't see everything is
  never a plain `GO`.
- Versioned JSON (`schema/readiness.schema.json`), a short Markdown report and the console, all
  masked by default.
- Endpoints come from `az cloud show`, for the engine and for `./nerdio fix`.
- Policy deployability stays with Nerdio's script until a read-only evaluation is proven; the
  report links it, and the kit never copies, wraps or re-hosts it.
- Writes, if any are ever needed, live in a separate probe tier that is off unless asked for by
  name and confirmed.

### Consequences

- Good, because a strict tenant can run every default check with Reader, and the pipeline can run
  it on every plan.
- Good, because the chat and the pipeline act on stable IDs and exit codes rather than parsing text.
- Bad, because some answers (policy denies, Nerdio's version, feature toggles inside Nerdio) can't
  be read today, so those checks report `manual` until Nerdio or Microsoft publish a way.

## More Information

Approved with the readiness spec on 2026-10-19 after a red-team review; built in phases (engine,
standalone zipapp, pre-install additions, post-install and post-wizard, features). The KB page is
[nerdio/readiness.md](../nerdio/readiness.md).

Phase 3 added the two opt-in tiers the spec allows: the Nerdio data tier (`--nerdio-data`,
read-only REST GETs signed in with the REST client, its secret from the kit's Key Vault or the
person's own shell) and one probe (`--probe url-check`, Run Command on one host after a typed
yes). The read-only policy evaluation spike is a no-go until a live sandbox run proves it, so
`sub.policy_eval` stays `manual`.
