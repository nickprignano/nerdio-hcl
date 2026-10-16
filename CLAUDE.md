# Nerdio HCL kit: notes for contributors

Terraform and Packer for deploying Nerdio Manager for Enterprise on Azure Virtual Desktop, built
to be turnkey: copy-paste, a button, or a guided chat. These notes are for people (and coding
assistants) changing the kit. The guided chat for people deploying it is the self-hosted setup
chatbot in `assistant/` ([docs/assistant.md](docs/assistant.md)).

## Layout that matters

- `schema/parameters.json` is the single source of truth for setup questions, defaults and
  validation. The chatbot, `./nerdio init` and the Actions form all read it.
- `scripts/nerdio/` is the engine behind `./nerdio` (Python standard library only).
- `assistant/` is the chatbot (its prompt is `assistant/prompt.md`); `modules/assistant` and
  `environments/example/00-assistant` deploy it.

## Rules

- **HCL first.** If Terraform can do it, Terraform does it. Scripts are thin glue.
- **Works from Azure Cloud Shell (Bash) in a browser.** No local-only tools; read IDs from `az account show`.
- **Public-safe repo.** No tenant or subscription IDs, domains, emails, IP ranges from real networks,
  secrets, or employer or customer names in anything committed. See
  [docs/knowledge/README.md](docs/knowledge/README.md#keep-it-public-safe).
- **No secrets in chat**, and nothing applied without a plan summary and an explicit yes.
- **Every change goes through a PR.** After touching the schema, engine or chatbot, run
  `./nerdio schema check`, `python3 -m unittest discover -s scripts/nerdio` and
  `python3 -m unittest discover -s assistant`.
