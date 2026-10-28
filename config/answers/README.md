# GitOps Answer Files (`config/answers/`)

Place non-identifying environment answer sets here as `config/answers/<env>.json` (for example,
`config/answers/sandbox.json`, `config/answers/dev.json`, or `config/answers/prod.json`) to drive
the deployment pipeline via Pull Requests and merges to `main`.

## How it works

1. **Pull Request (`pull_request` on `config/answers/*.json`):**
   - CI (`validate.yml` and `./nerdio schema check`) validates the JSON answers against
     [`schema/parameters.json`](../../schema/README.md), checks that no real tenant, subscription,
     or object GUIDs are committed ([Guardrail 4](../../docs/guardrails.md)), and verifies that
     Terraform accepts the rendered variables.
   - When `github.allow_pr_plans = true` is set in `00-pipeline`, `.github/workflows/deploy.yml`
     automatically runs a read-only `terraform plan` against `<env>-plan` and posts the redacted
     change summary on the run.
2. **Merge to `main` (`push` on `config/answers/*.json`):**
   - `.github/workflows/deploy.yml` automatically plans `platform` (and `config` once `01-platform`
     outputs exist in state), syncs the merged answers to the `answers/<env>.json` blob container,
     and pauses at the `<env>-apply` approval gate for a named reviewer to approve.
3. **Manual Dispatch & Chatbot Fallback:**
   - If `config/answers/<env>.json` is not present in the repository, `deploy.yml` falls back to
     reading `answers/<env>.json` from the pipeline's Azure Storage container (populated by
     `./scripts/pipeline/bootstrap.sh` or the self-hosted setup chatbot).

## Guardrail 4: What belongs in `config/answers/<env>.json`

- **Allowed:** `environment`, `location`, `additional_locations`, `identity_model`, `user_count`,
  `workload`, `address_space`, `prefix`, `_random4`, `enable_hardening`, `enable_vnet_runner`,
  `enable_resource_locks`, `vm_size`, `timezone_id`, and Entra group **display names** (resolved at
  plan time by the pipeline identity).
- **Never commit:** real `tenant_id`, `subscription_id`, Entra object/client GUIDs, real corporate
  domains, or secrets. Use Entra group display names instead of object GUIDs.
