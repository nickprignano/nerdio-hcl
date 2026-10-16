# Parameter schema

`parameters.json` is the single list of deployment parameters. The chat `setup` skill,
`./nerdio init` and the GitHub Actions form all read it, and each parameter maps onto a Terraform
variable in a stage. Change a question, default or rule here, never in one front door.

## A parameter

```json
{
  "id": "vm_size",
  "phase": "configure",
  "type": "string",
  "pattern": "^Standard_[A-Za-z0-9_]+$",
  "question": "Session host VM size?",
  "help": "Defaults from your workload answer.",
  "default": { "map": "workload", "values": { "light": "Standard_D4s_v5", "medium": "Standard_D8s_v5" } },
  "tfvars": [{ "stage": "config", "path": "host_pools.{host_pool_name}.vm_size" }],
  "sources": ["https://learn.microsoft.com/..."]
}
```

| Field | Meaning |
|---|---|
| `id` | Answer key, `--set` name and form input name |
| `phase` | `discover` or `configure` (the setup phases that ask questions) |
| `type` | `string`, `int`, `bool`, `enum`, `uuid`, `cidr`, `ipv4_list`, `group_list` (names or IDs, looked up with az), `principal_list` (also accepts `me`) |
| `question`, `help` | What every front door shows. Plain language; `help` says why it matters |
| `choices` | For `enum`: `value`, `label`, and `supported: false` plus `reason` for options the kit can't do yet |
| `pattern`, `min`, `max`, `min_prefix`, `max_prefix`, `min_items` | Validation, kept in step with the Terraform variable's own validation |
| `default` | A value; a template like `"st{prefix\|compact:15}fslogix"`; `{"map": "<id>", "values": {...}}`; or `{"derive": "<name>"}` for the derivations in `scripts/nerdio/engine.py` |
| `ask` | `always` (default), `advanced` (only with `--advanced`), or `never` (derived or read from the account) |
| `when` | Only active when earlier answers match, e.g. `{"fslogix_enabled": [true]}` |
| `source` | `tenant` or `subscription`: read from `ARM_*` or `az account show`, never asked or saved |
| `tfvars` | Where the value lands: `stage` (`platform`, `config`), a dotted `path` (may use `{id}`), and optional `value` template, `render` (`list`, `resource_groups`) or `omit_empty` |
| `form` | Show it on the Actions form. Keep the form to 10 inputs |
| `kb`, `sources` | What the chat skill cites: pages under `docs/knowledge/`, and external docs |
| `checks` | Cross-field checks, e.g. `subnets_in_address_space` |

Top level: `phases` (all eight, for the skills), `stages` (folder per stage), `output_file`,
`roots` (objects rendered as `null` when a feature is off) and `constants` (fixed tfvars such as tags).

## Checks

`./nerdio schema check` runs in CI. It checks the schema's own shape, that every `tfvars` path is a
declared variable, that each answer set in `examples/` renders and passes Terraform's variable
checks, and that the Actions form is in sync. Unit tests: `python3 -m unittest discover -s scripts/nerdio`.
