# Testing and CI

## terraform test

- Module tests with a mocked provider work without Azure credentials:

  ```hcl
  mock_provider "azurerm" {}

  run "plan" {
    command = plan
    # assertions...
  }
  ```

- Only plan-time values are checkable this way; anything computed by Azure is unknown.

## tflint

`.tflint.hcl` uses the `terraform` plugin with the `recommended` preset and the azurerm ruleset
(0.30.0 at last review). Run `tflint --init` then `tflint --recursive --minimum-failure-severity=error`.

## CI workflow

`.github/workflows/validate.yml` runs on pull requests and pushes to `main`:

- `hashicorp/setup-terraform@v3` with an exact `terraform_version` (1.16.6), then
  `terraform fmt -recursive -check`, `terraform validate` on the example root, `terraform test`
  on modules that have tests.
- `terraform-linters/setup-tflint@v4` for tflint.
- `hashicorp/setup-packer@v3` with an exact version (1.16.1), then `packer init`,
  `packer fmt -check` and `packer validate -var-file=example.pkrvars.hcl`.

Tips:

- Pin tool versions exactly in CI and pin actions to a release tag, not `@main`.
- If a local environment can't reach the registry, CI is a fine place to validate against
  providers you can't download locally.

_Last reviewed: 2026-10-16_
