---
status: proposed
date: 2026-11-10
decision-makers: [maintainers]
---

# 0034. One `cloud` setting, default commercial, for Azure Government (GCC High)

## Context and Problem Statement

The roadmap puts Azure Government (which GCC High tenants use) right after the first 90-day
window, because most of the work is our own code ([stack options](../stack-options.md)). An audit
on 2026-11-10 found the kit half-way there: `01-platform`, `modules/network`, `modules/nerdio-core`,
`modules/fslogix-storage` and the readiness engine already took a `cloud` value, but the
pipeline and chat stages, the GitHub federation audience, the workflows, Packer, the REST gap
filler's token endpoint, the chat's sign-in issuer and its Python data-plane calls were still
commercial-only. Public documentation also shows two things the kit can't fix itself: the
`nerdio/nme` provider signs in only to the commercial cloud, and Claude isn't offered inside
Azure Government. How should the kit target Government without changing anything for commercial
users or pretending the blocked parts work?

## Considered Options

- Wait: keep commercial-only until a Government subscription is available to test
- One `cloud` setting (`public` or `usgovernment`, default `public`) carried through every stage,
  module, workflow, script and Packer, with warnings where Government is known not to work
- A separate Government fork of the environment folders

## Decision Outcome

Chosen option: "One `cloud` setting", because every module added before it is one more place to
un-hard-code, the default keeps commercial plans unchanged, and the known blockers become visible
warnings instead of surprises.

- `cloud` comes from the setup question for the platform and config stages, and from
  `az cloud show` (or `ARM_ENVIRONMENT`) for the pipeline and chat bootstraps.
- Every Azure provider gets `environment = var.cloud`. Endpoints are looked up from `cloud`, never
  typed per module twice.
- The pipeline's GitHub federation uses the Government token-exchange audience
  (`api://AzureADTokenExchangeUSGov`) and publishes `NERDIO_CLOUD` to both GitHub environments,
  which the workflows read for `azure/login` and Packer.
- `check` blocks warn, without failing a plan, when stage 02 (`nerdio/nme`) or the chat (Claude)
  is pointed at Government.
- Only `public` and `usgovernment` are accepted. DoD (IL5) and other sovereign clouds stay out
  until Nerdio supports them.

### Consequences

- Good, because a commercial deployment's plan doesn't change, and a Government plan of stages
  00-pipeline and 01-platform is now possible.
- Good, because the blockers are named in code and in [government.md](../../government.md), with
  public sources.
- Bad, because nothing is tested in a Government subscription yet; documentation is the only
  evidence.
- Bad, because stage 02 and the chat still don't work in Government; this decision doesn't solve
  either.

## More Information

- Open question for the owner: how the setup chat serves a Government tenant (keep it commercial
  and drive only the pipeline, add an Azure OpenAI provider in Government, or no chat there).
  Record the answer as its own decision.
- Upstream ask (not sent): a token URL or cloud setting in the `nerdio/nme` provider.
- Revisit after the first Government spike (gap list in [government.md](../../government.md)).
