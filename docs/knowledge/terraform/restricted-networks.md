# Terraform and Packer behind a restrictive proxy

Some build environments (locked-down CI runners, sandboxes, corporate proxies) block
`registry.terraform.io` while still allowing `releases.hashicorp.com`. `terraform init` then
fails, e.g. `CONNECT tunnel failed, response 403`.

## What was reachable in one such environment

| Host | Result |
|---|---|
| `registry.terraform.io` | blocked (403) |
| `releases.hashicorp.com` | OK |
| GitHub release downloads / `api.github.com` | blocked |
| `git clone` of public GitHub repos | OK |
| `proxy.golang.org` | OK |

Check yours with `curl -sI https://<host>` before choosing a workaround.

## Workaround: filesystem mirror

1. Download Terraform, Packer and each provider zip from `releases.hashicorp.com`.
2. Lay out provider zips as
   `<mirror>/registry.terraform.io/hashicorp/<name>/terraform-provider-<name>_<version>_linux_amd64.zip`.
3. Write a CLI config:

   ```hcl
   provider_installation {
     filesystem_mirror {
       path = "/path/to/mirror"
     }
   }
   ```

4. `TF_CLI_CONFIG_FILE=/path/to/tfrc terraform init -backend=false`. Providers install as
   "(unauthenticated)", which is expected for a filesystem mirror.

Providers that only publish to GitHub releases (not `releases.hashicorp.com`) can't be fetched
this way. Build them from a git clone instead, as with `nerdio/nme`
([../nerdio/terraform-provider.md](../nerdio/terraform-provider.md#building-it-locally)).

## Packer plugins

1. Download `packer-plugin-azure_<version>_linux_amd64.zip` from `releases.hashicorp.com`.
2. Unzip and `chmod +x` the binary. Without it: `fork/exec ... permission denied`.
3. `packer plugins install --path <binary> github.com/hashicorp/azure`, with `PACKER_PLUGIN_PATH` set.

_Last reviewed: 2026-10-16_
