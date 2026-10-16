---
status: proposed
date: 2026-10-16
decision-makers: [maintainers]
---

# 0015. Secrets: Key Vault by default; OpenBao as the optional Vault-style module

## Context and Problem Statement

Stage 2 of the kit (`nerdio/nme`) needs the Nerdio REST API client secret that stage 1 creates.
Today that secret is handed over by hand. The roadmap wanted it short-lived and never in tfvars,
the shell or the repo. Should the kit run HashiCorp Vault, its open-source fork OpenBao, or neither?

Facts checked on 2026-10-16:

- **Vault license:** Vault is BSL 1.1, and the licensor is now IBM. The Additional Use Grant allows
  production use unless it's offered to third parties as a hosted or embedded product that competes
  with IBM's paid versions. It says "Products that are not provided on a paid basis are not
  competitive", and internal use isn't competitive. So a free community kit that tells users to
  run Vault is fine. Each release converts to MPL 2.0 after four years.
- **Signing in to Azure without a secret:** the Azure secrets engine's plugin workload identity
  federation is Vault Enterprise only. Vault Community and OpenBao can both use an Azure managed
  identity instead of a client secret when they run in Azure. The OpenBao Azure plugin docs say
  `client_id` and `client_secret` "may be omitted" with MSI. So a stored secret is only needed
  when Vault runs outside Azure.
- **OpenBao** Azure plugin v0.23.0 (September 2025) supports managed identity and roles on an
  existing app (`application_object_id`), but has no plugin workload identity federation.
- **Permissions:** for Vault or OpenBao to mint secrets on the existing REST client app, its own
  identity needs Graph `Application.ReadWrite.All`, a high privilege.
- **Nerdio's provider** only accepts a client secret (`internal/provider/provider.go`), so some
  secret has to exist until Nerdio adds federated sign-in.

## Considered Options

- Azure Key Vault plus GitHub OIDC, with an ephemeral read
- HashiCorp Vault Community minting a short-lived secret per run
- OpenBao minting a short-lived secret per run

## Decision Outcome

Chosen option: "Key Vault plus GitHub OIDC" as the default, because it needs nothing extra to run
and fits [0009](0009-prefer-azure-github-hashicorp-oss.md) (Azure first) and the turnkey goal.

- **Default:** stage 1 writes the Nerdio REST secret to Azure Key Vault. Stage 2 reads it with an
  ephemeral resource, signed in with GitHub OIDC, so the secret never lands in tfvars, state, the
  shell or logs.
- **Optional advanced module:** OpenBao (MPL-2.0) hosted in Azure with a managed identity. It
  mints a short-lived secret per run, so no long-lived Nerdio secret exists anywhere. Vault
  Community works the same way for people who already run Vault.
- **Real fix, upstream:** workload identity federation in the `nme` provider, which removes the
  secret entirely ([upstream ask](../nerdio/upstream-contributions.md#feature-gaps)).

### Consequences

- Good, because the default adds no service to operate and no extra license question.
- Good, because the optional module removes the long-lived secret for those who want it, using
  open-source software.
- Bad, because the default still keeps one long-lived secret, in Key Vault, until Nerdio's
  provider supports federated sign-in.
- Bad, because the optional module needs Graph `Application.ReadWrite.All` for its identity.

## More Information

*Unverified:* whether the Terraform `vault` provider's ephemeral resources work against OpenBao.
OpenBao is API-compatible with Vault by design.

Sources: the `hashicorp/vault` LICENSE file; [Vault Azure secrets engine](https://developer.hashicorp.com/vault/docs/secrets/azure);
the `openbao/openbao-plugins` `secrets/azure` docs; Nerdio's `NME-Terraform-Provider` source.
Proposed in the roadmap (build item 2); status changes to accepted once the maintainer confirms.
