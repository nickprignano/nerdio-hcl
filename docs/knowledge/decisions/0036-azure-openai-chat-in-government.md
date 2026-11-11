---
status: proposed
date: 2026-11-11
decision-makers: [maintainers]
---

# 0036. In Azure Government the setup chat uses Azure OpenAI in the same tenant

## Context and Problem Statement

[Decision 0034](0034-azure-government-cloud-parameter.md) let the kit target Azure Government, but
left the setup chat without a model there: Claude isn't offered inside Azure Government (no
Foundry regions, and the Claude API's federation guide covers only the commercial Entra issuer),
and both Claude paths would send prompts outside the Government boundary. The owner's rule for a
Government deployment is that everything stays in the Government tenant. How does the chat serve a
Government tenant without leaving it, and without changing anything for commercial users?

## Considered Options

- Keep the chat in a commercial tenant and drive a Government deployment only through the pipeline
- No chat in Government: `./nerdio init` plus the pipeline
- An Azure OpenAI model provider, deployed by the chat's own Terraform into the Government tenant
  and a Government region, called with the app's managed identity

## Decision Outcome

Chosen option: "An Azure OpenAI model provider", because it is the only option that keeps the
chat-first setup (decision 0017) in Government while keeping every prompt, answer and token inside
the Government tenant.

- `modules/assistant` gains `model_provider = "azure-openai"`. Left unset, `model_provider` picks
  by cloud: `claude-api` in commercial Azure (unchanged, decision 0020), `azure-openai` in
  Government. In Government, `claude-api` and `foundry` are refused by validation, not just warned.
- Terraform creates an Azure OpenAI account (`kind = "OpenAI"`, key access off) and a model
  deployment in `usgovvirginia` or `usgovarizona`, in the chat's resource group, and gives the
  app's managed identity **Cognitive Services OpenAI User** on that account only. Default model:
  `gpt-4.1` (2025-04-14) on a regional `Standard` deployment, offered in both Government regions.
  Global SKUs are refused because they route outside the region's boundary.
- The app asks Entra for a token with the scope `https://cognitiveservices.azure.us/.default` and
  calls `https://<account>.openai.azure.us`. No API key exists anywhere.
- A small adapter (`assistant/azure_openai.py`, standard library only) translates the agent loop's
  Claude-shaped request and reply to Chat Completions, so the tools, prompt, logs and the
  transcript the browser keeps are the same for every provider.

### Consequences

- Good, because a Government deployment can be set up chat-first without any prompt leaving the
  Government tenant, and commercial deployments plan exactly as before.
- Good, because it stays keyless and least privilege: one data-plane role on one account.
- Bad, because the chat's prompt and tools were tuned on Claude; a GPT model may follow them less
  well. The model is a setting, so a better Government model can replace it without code changes.
- Bad, because nothing is tested in a Government subscription yet: the model's tool use with this
  prompt, Container Apps availability, quota for the default model, and the `2024-10-21` API
  version there are documentation only.
- Neutral: the Azure OpenAI account is billed through the Government subscription, per token.

## More Information

- Sources: [Azure OpenAI models in Azure Government](https://learn.microsoft.com/azure/ai-foundry/openai/azure-government)
  (regions and SKUs), [Compare Azure Government and global Azure](https://learn.microsoft.com/azure/azure-government/compare-azure-government-global-azure#guidance-for-developers)
  (`openai.azure.us`), [Azure OpenAI client library](https://learn.microsoft.com/dotnet/api/overview/azure/ai.openai-readme)
  (`cognitiveservices.azure.us` scope), [Managed identity for Azure OpenAI](https://learn.microsoft.com/azure/ai-foundry/openai/how-to/managed-identity)
  (Cognitive Services OpenAI User).
- Details and the Government spike list: [government.md](../../government.md) and
  [assistant.md](../../assistant.md#azure-openai-in-azure-government).
- Revisit when Claude is offered inside Azure Government, or after the first Government spike.
