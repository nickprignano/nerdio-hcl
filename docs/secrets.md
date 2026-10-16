# REST API secret hand-off

Stage 2 (`nerdio/nme`) signs in to Nerdio's REST API with the REST client app that stage 1
creates. Nerdio's provider only accepts a client secret today, so some secret has to reach
stage 2. The kit moves it without anyone copying, exporting or pasting it
([decision 0015](knowledge/decisions/0015-secrets-key-vault-default-openbao-optional.md)).

Pick the hand-off with `nme_secret_store` in `01-platform`:

| `nme_secret_store` | What happens | Long-lived secret? | Extra to run |
|---|---|---|---|
| `key_vault` (default) | Stage 1 writes the secret to its own Key Vault. Stage 2 reads it on the fly with your `az` sign-in or GitHub OIDC. | Yes, in Key Vault and stage 1 state | Nothing |
| `openbao` | An OpenBao server adds a short-lived password to the REST client app for each run. | No | One small VM |
| `output` | The old way: `export NME_CLIENT_SECRET="$(terraform output -raw nme_client_secret)"`. | Yes, and it passes through your shell | Nothing |

The real fix is upstream: if Nerdio's provider accepted federated credentials, there would be no
secret at all. That ask is in [upstream-contributions.md](knowledge/nerdio/upstream-contributions.md).

## Key Vault (default)

`modules/nerdio-secrets` creates a small RBAC-only Key Vault next to Nerdio Manager and stores the
secret with a write-only attribute, so its own resources never hold the value. Stage 2 reads it
with the ephemeral `azurerm_key_vault_secret` resource and passes it straight to the provider. It
never lands in tfvars, the shell, logs or stage 2's state.

- **Who can read it:** you (the identity running stage 1), plus `nme_secret.reader_object_ids`.
  Each reader gets **Key Vault Secrets User** on that one secret, and **Reader** on the vault so
  Terraform can look up its address. Reader doesn't grant access to secret values.
- **GitHub Actions:** set `nme_secret.github_oidc = { repository = "owner/name" }`. Stage 1 creates
  a user-assigned identity that trusts that repository's `sandbox` environment through OIDC, and
  outputs its `github_oidc_client_id` for `azure/login`. The pipeline stores no Azure secret.
- **Rotation:** the secret rotates with `secret_rotation_days`; the next stage 1 apply writes the
  new value to Key Vault, and the Key Vault copy carries the same expiry date.
- **What's left:** the secret also sits in stage 1's state, because `azuread_application_password`
  returns it. Keep stage 1 state in a protected backend.

Nothing to do in Cloud Shell: `./scripts/cloudshell-bootstrap.sh config` works as before, and
`terraform destroy` in stage 2 reads the secret the same way.

## OpenBao (optional)

`modules/openbao` runs [OpenBao](https://openbao.org) (MPL-2.0, the open-source fork of Vault) on
one small Linux VM. Each plan or apply logs in and gets a fresh password on the REST client app,
valid for `credential_ttl` (2 hours by default), which OpenBao then revokes. Stage 1 creates no
long-lived secret at all.

```hcl
# 01-platform/terraform.tfvars
nme_secret_store = "openbao"
openbao = {
  subnet_cidr              = "10.50.4.64/28"   # a free /28 in the AVD VNet
  allowed_source_addresses = ["Internet"]      # or your own CIDRs
}
```

How it stays turnkey and safe:

- **No unseal keys or root token to handle.** OpenBao auto-unseals with a Key Vault key and
  configures itself from its config file on first start (self-initialization), then revokes the
  root token it used. The VM is disposable: replacing it rebuilds the same server.
- **Least privilege.** The VM's managed identity owns the REST client app and has Graph
  `Application.ReadWrite.OwnedBy`, so it can only manage passwords on apps it owns, not every app
  in the tenant. On Key Vault it can only wrap and unwrap with the unseal key and read its own TLS
  certificate.
- **Login without passwords.** Cloud Shell users log in with an Entra token issued for OpenBao's
  own login app (never an Azure management token, which could be replayed). GitHub Actions jobs
  log in with their OIDC token when `nme_secret.github_oidc` is set. Only the users in
  `openbao.login_object_ids` (and you) can log in.
- **Small surface.** Only HTTPS on 8200 is open, from `allowed_source_addresses`. There's no SSH
  rule and no UI. TLS uses a certificate that Key Vault generates and renews; the VM picks up
  renewals daily.
- **Pinned downloads.** The VM installs the OpenBao release by SHA-256 and the Azure plugin by
  image digest (`openbao_version` and `azure_plugin_image` in the module).

In Cloud Shell, `./scripts/cloudshell-bootstrap.sh config` writes `02-nerdio-config/openbao-ca.pem`
from stage 1 and puts a short-lived Entra token for OpenBao in `TF_VAR_openbao_jwt`. That token
only works for OpenBao, and it isn't the Nerdio secret. By hand:

```bash
cd environments/<env>/01-platform
terraform output -json nerdio_config_inputs > ../02-nerdio-config/platform.auto.tfvars.json
terraform output -raw openbao_ca_cert > ../02-nerdio-config/openbao-ca.pem
export TF_VAR_openbao_jwt="$(az account get-access-token \
  --scope "$(terraform output -json nerdio_config_inputs | jq -r .openbao.scope)" \
  --query accessToken -o tsv)"
cd ../02-nerdio-config && terraform init && terraform plan
```

When Key Vault renews the TLS certificate, run stage 1 again (or `terraform refresh`) and rewrite
`openbao-ca.pem`.

Vault Community works the same way for people who already run Vault: point the `vault` provider
in stage 2 at it and configure the same Azure secrets role. Its license (BSL 1.1) allows that for
internal use; see decision 0015.

## Must test live

None of this has run against a real tenant yet. Check these on the first sandbox run:

- Stage 2 reads the secret from Key Vault in Cloud Shell, and stage 2's state has no copy of it.
- The OpenBao VM boots, unseals with Key Vault, downloads the Azure plugin and finishes
  self-initialization (`sudo journalctl -u openbao` through Run Command or Serial Console).
- `Application.ReadWrite.OwnedBy` plus ownership is enough for the Azure plugin to add and remove
  passwords on the REST client app. OpenBao's docs list `Application.ReadWrite.All` for existing
  apps; if OwnedBy fails, that's the fallback, and it's a much broader permission.
- A freshly minted password works on the first try. Entra can take a few seconds to accept a new
  password; if the first plan fails to sign in, retry it and note it in the known-errors catalog.
- `az account get-access-token --scope api://<login app>/login` works in Cloud Shell without a
  consent prompt (Azure CLI is pre-authorized on the login app).
