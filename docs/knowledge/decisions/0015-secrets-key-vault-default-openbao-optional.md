---
status: accepted
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
- Bad, because the optional module needs a Graph application permission for its identity. The
  build narrows it to `Application.ReadWrite.OwnedBy` by making that identity an owner of the
  REST client app; if that proves not enough live, the fallback is `Application.ReadWrite.All`.

## More Information

Accepted by the maintainer on 2026-10-16 and built as `modules/nerdio-secrets` (default) and
`modules/openbao` (optional), selected with `nme_secret_store` in stage 1. How it works and what
to check on the first live run: [docs/secrets.md](../../secrets.md). Choices made while building:

- The Key Vault copy is written with the write-only `value_wo`, and stage 2 reads it with the
  ephemeral `azurerm_key_vault_secret`, so only stage 1's state still holds the value. Readers get
  Key Vault Secrets User on the one secret, plus Reader on the vault, because the azurerm provider
  looks up the vault's URI through Azure Resource Manager.
- OpenBao runs on one VM with Key Vault auto-unseal and self-initialization, so no unseal key or
  root token is ever handed out. Its Azure plugin is pulled by digest from OpenBao's registry.
  Cloud Shell users log in with an Entra token for a dedicated login app (with Azure CLI
  pre-authorized), not an Azure management token, which OpenBao could otherwise replay.
- Adding the `azurerm` and `vault` providers to stage 2 meant replacing Nerdio's documented
  `dev_overrides` install, which breaks `terraform init` for other providers, with a local plugin
  directory. It's still the user's own download from Nerdio's release (decision 0013).
- The kit's minimum Terraform is now 1.11, for write-only attributes.

*Unverified until a live run:* that OpenBao's Azure plugin can manage passwords with
`Application.ReadWrite.OwnedBy` (its docs list `Application.ReadWrite.All` for existing apps), and
that the `vault` provider's `vault_azure_access_credentials` works against OpenBao. The OpenBao
config was checked locally against the real 2.7.1 binary: it self-initializes and accepts the
Entra login settings.

Sources: the `hashicorp/vault` LICENSE file; [Vault Azure secrets engine](https://developer.hashicorp.com/vault/docs/secrets/azure);
the `openbao/openbao-plugins` `secrets/azure` docs; Nerdio's `NME-Terraform-Provider` source.
Proposed in the roadmap (build item 2); status changes to accepted once the maintainer confirms.
