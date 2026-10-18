---
title: "Nerdio Manager's AI features"
summary: "Copilot, ScriptPro, AnalyticsPro and the MCP connector: what they run on, and how they relate to the kit's setup chat"
topic: nerdio
status: partial
last_reviewed: 2026-10-18
---

# Nerdio Manager's AI features

Nerdio Manager has its own AI features. They are separate from the kit's setup chat
([decision 0020](../decisions/0020-claude-api-federation-for-the-chat.md)): the chat helps you
*deploy* Nerdio, while these help you *run* it once it's up.

## What they run on

- **Copilot** (help questions), **ScriptPro** (script generation) and **AnalyticsPro** (KQL
  queries) use Azure OpenAI resources that Nerdio deploys into a resource group you pick, in your
  own tenant. You choose the OpenAI model from what your quota allows, and the deployment type
  (Data Zone Standard or Global Standard). Billed per token through Azure; no standing cost when
  unused. ([Manage Nerdio Copilot](https://nmehelp.getnerdio.com/hc/en-us/articles/30352365570957),
  [data security](https://nmehelp.getnerdio.com/hc/en-us/articles/32928743596045-Data-Security-and-Privacy-with-Azure-OpenAI-in-Nerdio-Manager))
- They need **Azure OpenAI quota**, which is Microsoft's per-request process, like the Claude on
  Foundry quota the kit's first trial tenant was denied. Whether OpenAI quota is easier to get is
  unverified.
- They're **OpenAI only** today. Choosing other models, Claude included, is a community request
  Nerdio says is in its queue, with no date
  ([request](https://nmehelp.getnerdio.com/hc/en-us/community/posts/41823153081869-Let-Nerdio-Manager-Copilot-use-configurable-Azure-AI-models-gpt-5-1-chat-claude-sonnet-4-5-etc)).
- Turning Copilot on is a **portal step** (System > Settings > Nerdio > Nerdio Manager Copilot).
  No API or Terraform resource is documented, so the kit can only guide it. Disabling it leaves a
  Smart Detector alert rule behind (the same kind of leftover as the known error
  `smart-detection-action-group-blocks-destroy`).
- Other AI items in the same help section: a PII detector, description generation and auto-scale
  insights ([section](https://nmehelp.getnerdio.com/hc/en-us/sections/29088944940173-AI-and-Nerdio-Manager)).

## The MCP connector (public preview)

- Lets an AI agent read live data from Nerdio Manager: workspaces, host pools, profiles, images,
  storage and logs. The documented permission is *Read*.
- An HTTP endpoint on the Nerdio web app (`https://nmw-app-<instance>.azurewebsites.net/mcp`),
  turned on under System > Settings > Integrations > Model Context Protocol by a Nerdio Admin.
  Users sign in through a browser OAuth flow; agents that can't do OAuth use a "bridging" app
  registration that isn't documented in detail.
  ([MCP connector](https://nmehelp.getnerdio.com/hc/en-us/articles/49256623957133-Nerdio-Manager-MCP-Connector))

## How it fits the kit

- **Not on the setup path.** Nothing in the kit needs Nerdio's AI features, and they don't need
  the kit's chat. Leave them off by default; a tenant that wants them turns Copilot on after the
  wizard, with its own Azure OpenAI quota.
- **The MCP connector is the interesting one.** Read-only live data is exactly what the chat's
  *verify* and *handover* phases lack (chatbot-first inventory, step 20): the chat could confirm
  the workspace, host pools and profiles exist as planned. Open questions before building on it:
  whether a server-side app can call it as the signed-in admin (the OAuth flow is per user), how
  the bridging app registration works, and whether it stays read-only.
- **Upstream asks:** an API or Terraform setting to enable Copilot and the MCP connector, model
  choice (Claude through Foundry or the Claude API), and documentation for the bridging app.
