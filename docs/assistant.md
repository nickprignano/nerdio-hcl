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
| Claude on Microsoft Foundry | An AI Services resource with a Claude deployment, billed through your Azure subscription |
| Managed identity | How the app calls the model. Key-based access is turned off on the Foundry resource, so there's no API key to store or leak |
| Log Analytics | App logs, kept 30 days |

All of it is Terraform: `modules/assistant`, deployed by `environments/example/00-assistant`.

## Deploy it

In Azure Cloud Shell (Bash), signed in to the tenant and subscription you're setting up:

```bash
git clone https://github.com/nickprignano/nerdio-hcl ~/nerdio-hcl && cd ~/nerdio-hcl
./nerdio assistant --admin-group "AVD Admins"
```

It reads the tenant and subscription from `az account show`, writes
`00-assistant/assistant.auto.tfvars.json` (gitignored), and runs `terraform apply`. Review the plan
and type `yes`. When it finishes, it prints the URL. Open it and sign in.

Options: `--location` (the app's region, default `eastus2`), `--foundry-location` (a region that
offers Claude on Foundry, if different), `--image` (your own build), and `--plan` to only plan.

**You need:**
- Owner on the subscription, or Contributor plus User Access Administrator, because the app's
  identity gets a role on the Foundry resource.
- Rights to create an app registration and assign a group to it (Application Administrator or
  Cloud Application Administrator).
- An existing Entra security group for the admins who'll use the chat.
- Access to Claude models in Microsoft Foundry for your subscription and region. If Terraform can't
  create the model deployment, create it in the Foundry portal and set
  `foundry = { create_deployment = false, deployment_name = "<its name>" }` in the tfvars.

## Put it on your home screen

The chat installs like an app, with no App Store and nothing to pay for. On an iPhone or iPad, open
the URL in Safari or Edge, sign in, tap **Share**, then **Add to Home Screen**. In Edge or Chrome on
a computer, use **Install** in the address bar. It opens full screen with its own icon, and
sign-in works the same way as in the browser.

## How it works

- **Nothing in your tenant is changed by the chat.** The bot's tools only read the kit's schema
  and knowledge base. When something has to run in your tenant (the readiness check, writing the
  configuration), it gives you one Cloud Shell command to paste, and you paste the output back.
- **No IDs or secrets in the conversation.** Tenant and subscription IDs come from your Cloud Shell
  sign-in, and group names are looked up there. The bot never asks for a password, key or secret.
- **No stored conversations.** The app keeps no state. The conversation lives in your browser, so
  it survives switching to Cloud Shell and back. It's cleared when you click **New**, after a week
  unused, or when a different admin signs in on the same browser.
- **Grounded answers.** Each recommendation comes from the question's help text, the knowledge base
  in `docs/knowledge/`, or the documentation it links. When there's no source, it says so.

## Cost

The Container App costs nothing while idle (it scales to zero) and a little while you chat. Model
use is billed per token through Azure. Log Analytics bills per GB ingested, which is small here.
Remove it all with `terraform -chdir=environments/example/00-assistant destroy`.

## The image

GitHub Actions builds the app from `assistant/Dockerfile` and publishes it to
`ghcr.io/nickprignano/nerdio-hcl-assistant` on every merge to main. Pull requests only build it.
For production, pin a digest with `--image ghcr.io/…@sha256:…`. To build your own from Cloud Shell
without Docker, use `az acr build` into your own registry and pass its image with `--image`.

## Not yet verified on a live tenant

- That Terraform's `azurerm_cognitive_deployment` with model format `Anthropic` creates the Claude
  deployment. The fallback is the portal plus `create_deployment = false`.
- That the **Cognitive Services User** role is enough for the managed identity to call Claude on Foundry.
- Sign-in with ID tokens only (no client secret) on Container Apps authentication.
