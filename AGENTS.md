# Instructions for AI assistants

Read [docs/guardrails.md](docs/guardrails.md) before changing anything. These are not optional:

- Never put real tenant, subscription, object or resource IDs, domains, IPs, emails, secrets, or
  employer or customer names in the repo, the knowledge base, commits or PR text.
- Never ask for, show or store a secret in chat. The user runs the step that handles it.
- Propose changes as pull requests. Never run `terraform apply` against a user's tenant; plan,
  explain, and let the tenant owner apply.
- HCL first: do it in Terraform or Packer if they can; scripts are thin bootstrap glue.
- Every step must work from Azure Cloud Shell (Bash) in a browser, on an iPad included.
- Code from Get-Nerdio repositories and MB-External/NME-Terraform is unlicensed: use facts from
  it, never copy or adapt it, and never vendor Nerdio binaries.
- Run the prior-art check (`python3 scripts/kb/prior_art.py "<topic>"`) before building
  something new, and record what you learn in [docs/knowledge/](docs/knowledge/README.md).

## Layout that matters

- `schema/parameters.json` is the single source of truth for setup questions, defaults and
  validation. The setup chatbot, `./nerdio init` and the Actions form all read it.
- `scripts/nerdio/` is the engine behind `./nerdio` (Python standard library only).
- `assistant/` is the self-hosted setup chatbot (its prompt is `assistant/prompt.md`);
  `modules/assistant` and `environments/example/00-assistant` deploy it. See [docs/assistant.md](docs/assistant.md).
- After touching the schema, engine or chatbot, run `./nerdio schema check`,
  `python3 -m unittest discover -s scripts/nerdio` and `python3 -m unittest discover -s assistant`.
