# Setup chatbot

A guided chat for setting up the kit. You host it in your own Azure tenant, the one you're deploying
Nerdio into, and it walks you through discover, a readiness check and configure. It asks the same
questions as `./nerdio init` and the Actions form, because all three read
[`schema/parameters.json`](../schema/README.md).

## What gets deployed

| Piece | What it is |
|---|---|
| Container App | The chat web app. Scales to zero when nobody is using it |
| Entra sign-in | Container Apps authentication with an app registration. Only members of the admin group you name can sign in |
| Claude | The [Claude API](#claude-api), billed to your Anthropic organization. [Claude on Microsoft Foundry](#claude-on-foundry), billed through Azure, is optional if Microsoft grants you quota. Pick with `--model-provider` |
| Managed identity | How the app calls Claude, either way. There's no API key to store or leak |
| Log Analytics | App logs, kept 30 days |

All of it is Terraform: `modules/assistant`, deployed by `environments/example/00-assistant`.

## Deploy it

In Azure Cloud Shell (Bash), signed in to the tenant and subscription you're setting up:

```bash
git clone https://github.com/nickprignano/nerdio-hcl ~/nerdio-hcl && cd ~/nerdio-hcl
./nerdio assistant --admin-group "AVD Admins"
```

It reads the tenant and subscription from `az account show` (checked against `./nerdio use`, if
you've [pinned an environment](pipeline.md#enter-the-tenant-and-subscription-once)), writes
`00-assistant/assistant.auto.tfvars.json` (gitignored), and runs `terraform apply`. Review the plan
and type `yes`. When it finishes, it prints the URL. Open it and sign in.

With the Claude API (the default), connect it once afterwards, as described under
[Claude API](#claude-api). Until then the chat opens but says it isn't connected yet.

Options: `--model-provider claude-api|foundry`, `--location` (the app's region, default
`eastus2`), `--foundry-location` (a region that offers Claude on Foundry, if different), `--image`
(your own build), and `--plan` to only plan.

**You need** (the full list, with reasons, is in [access.md](access.md)):
- On the subscription, rights to create the resources and the app's role assignments: Owner, or
  Contributor plus Role Based Access Control Administrator.
- Rights to create app registrations and assign a group to one (Application Administrator or
  Cloud Application Administrator).
- An existing Entra security group for the admins who'll use the chat.
- For the Claude API: an admin of your Anthropic organization, once. For Foundry: access to
  Claude models in Microsoft Foundry for your subscription and region.

## Claude API

The main path. The chat signs in to the Claude
API with **workload identity federation**: its managed identity gets a token from Entra for an
audience app the kit creates, and the Claude API trades that for an access token that lasts ten
minutes and can only call the model. No API key is created, stored or passed around, and the
Claude side trusts exactly one identity: this app's, by object ID, in this tenant.

Connect it once, in Cloud Shell, as an admin of your Anthropic organization:

```bash
./scripts/install-ant-cli.sh                     # Anthropic's CLI, into ~/.local/bin
ant auth login --no-browser --profile nerdio-admin --scope org:admin
./nerdio assistant --connect-claude
ant auth logout --profile nerdio-admin           # drop the admin sign-in when done
```

`ant auth login` prints a link; open it, approve, and paste the code back. Then
`--connect-claude` reads what the rule must match from Terraform's `claude_federation` output and,
through Anthropic's Admin API, creates or reuses:

| On the Claude side | Settings |
|---|---|
| Workspace named after the chat (`nme-assistant`) | Its own usage and spend limits |
| Federation issuer for your tenant | `https://login.microsoftonline.com/<tenant>/v2.0`, keys from Entra's discovery document, accepts Entra tokens up to 24 hours old (Azure issues managed identity tokens that long) |
| Service account `nme-assistant-chat` | Developer organization role, *user* role in that workspace |
| Federation rule `nme-assistant-chat` | Matches the token's audience, the app's exact object ID and your tenant ID; scope `workspace:inference`; 10-minute tokens |

It saves the resulting IDs (none are secrets) in the gitignored tfvars and applies again so the app
uses them. Rerunning it is safe: it finds everything by name, and repoints the rule if the app's
identity was recreated. The admin token is read from the `ant` CLI, sent only to
`api.anthropic.com`, and never printed or written by the kit.

If your organization doesn't allow admin tokens in a shell, run
`./nerdio assistant --connect-claude --console` instead. It prints the same values for the
Claude Console's **Connect workload** wizard, then you pass the IDs it shows with
`./nerdio assistant --claude-ids org=…,rule=fdrl_…,account=svac_…,workspace=wrkspc_…`.

To revoke access, archive the rule in the Claude Console (or delete the chat's managed identity).
To switch to Foundry, run `./nerdio assistant --model-provider foundry`; the audience app
goes away and the rule simply stops matching anything.

## Claude on Foundry

Optional. Microsoft grants Claude-on-Foundry quota per request and can deny it (it did for the
kit's first trial tenant), so plan on the Claude API unless you already have quota. With `--model-provider foundry`, Terraform creates an AI Services resource with a Claude
deployment and gives the app's identity **Cognitive Services User** on it. Key-based access is
turned off on the resource. If Terraform can't create the model deployment, create it in the
Foundry portal and set `foundry = { create_deployment = false, deployment_name = "<its name>" }`
in the tfvars.

## Put it on your home screen

The chat installs like an app, with no App Store and nothing to pay for. On an iPhone or iPad, open
the URL in Safari or Edge, sign in, tap **Share**, then **Add to Home Screen**. In Edge or Chrome on
a computer, use **Install** in the address bar. It opens full screen with its own icon, and
sign-in works the same way as in the browser.

## How it works

- **Nothing in your tenant is changed by the chat.** The bot's tools only read the kit's schema
  and knowledge base. When something has to run in your tenant (the readiness check, writing the
  configuration), it gives you one Cloud Shell command to paste, and you paste the output back.
- **Deploying from the chat** is optional: connect it to the [deploy pipeline](pipeline.md#connect-the-chatbot)
  with `--pipeline`, then open `/setup/github` once to create its GitHub App in two clicks. Then
  it can save your answers for the pipeline, run the readiness check, start a plan and explain it,
  explain a failed run from its log, and guide you through Nerdio's wizard with the exact names. It can ask for an apply
  but can't approve one: that's you, in GitHub. Its identity gets no Azure rights beyond two blob
  containers and its own Key Vault, which holds only the GitHub App's key.
- **No IDs or secrets in the conversation.** Tenant and subscription IDs come from your Cloud Shell
  sign-in, and group names are looked up there. The bot never asks for a password, key or secret.
- **No stored conversations.** The app keeps no state. The conversation lives in your browser, so
  it survives switching to Cloud Shell and back. It's cleared when you click **New**, after a week
  unused, or when a different admin signs in on the same browser.
- **Grounded answers.** Each recommendation comes from the question's help text, the knowledge base
  in `docs/knowledge/`, or the documentation it links. When there's no source, it says so.

## Cost

The Container App costs nothing while idle (it scales to zero) and a little while you chat. Model
use is billed per token: by Anthropic to your organization's workspace with the Claude API, or
through Azure with Foundry. Log Analytics bills per GB ingested, which is small here.
Remove it all with `terraform -chdir=environments/example/00-assistant destroy`.

The model defaults to `claude-opus-5-5` at `medium` effort ([decision 0022](knowledge/decisions/0022-family-model-selection-convention.md)).
Change them with `effort` and `claude_api.model` in the stage's tfvars; raise effort before changing the model.
Every model call writes one `model_call` JSON line to the app's log with the model, effort, step,
`stop_reason`, latency and token counts (input, output, cache read and cache write). Each chat turn
then writes one `chat_turn` line with the same `turn` ID, its outcome (`completed`, `refusal`,
`max_tokens`, `step_limit` or `error`), the number of model calls and tool errors, the turn's total
latency and summed tokens. A turn is the pilot's task, so the turn lines give tokens per completed
task and the failure rate. These lines never hold the conversation, answers, error text or
credentials. To see what setups cost, from Cloud Shell:

```bash
az monitor log-analytics query -w "$(az monitor log-analytics workspace list -g rg-nme-assistant --query '[0].customerId' -o tsv)" \
  --analytics-query 'ContainerAppConsoleLogs_CL | where Log_s has "\"model_call\"" | extend r = parse_json(Log_s)
  | summarize calls = count(), input = sum(toint(r.input_tokens)), output = sum(toint(r.output_tokens)),
    cache_read = sum(toint(r.cache_read_input_tokens)), cache_write = sum(toint(r.cache_creation_input_tokens)),
    p50_ms = percentile(toint(r.latency_ms), 50) by tostring(r.model), tostring(r.effort), bin(TimeGenerated, 1d)'
```

The pilot's per-turn numbers and how to report them are in [model-pilot.md](model-pilot.md).

## The image

GitHub Actions builds the app from `assistant/Dockerfile` and publishes it to
`ghcr.io/nickprignano/nerdio-hcl-assistant` on every merge to main. Pull requests only build it.
For production, pin a digest with `--image ghcr.io/…@sha256:…`. To build your own from Cloud Shell
without Docker, use `az acr build` into your own registry and pass its image with `--image`.

## Not yet verified on a live tenant

- The Claude API path end to end: the managed identity token exchange, the `workspace:inference`
  scope with a *user* workspace role, and the Admin API calls `--connect-claude` makes (issuer
  lifetime, rule update). If the chat gets a 403 from the Claude API, give the service account the
  *developer* role in its workspace in the Claude Console.

- That Terraform's `azurerm_cognitive_deployment` with model format `Anthropic` creates the Claude
  deployment. The fallback is the portal plus `create_deployment = false`.
- That the **Cognitive Services User** role is enough for the managed identity to call Claude on Foundry.
- Sign-in with ID tokens only (no client secret) on Container Apps authentication.
