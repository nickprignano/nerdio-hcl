"""ai.*: what Nerdio's Copilot needs from Azure OpenAI before it's turned on (feature `ai`)."""

from __future__ import annotations

from ..model import check

KB = "docs/knowledge/nerdio/ai-features.md"
DEPLOY_TYPES = ("GlobalStandard", "DataZoneStandard")
QUOTA_FORM = "https://aka.ms/oai/stuquotarequest"


@check("ai.provider", "Cognitive Services provider", needs="Reader on the subscription", kb=KB, features=["ai"],
       source="https://learn.microsoft.com/azure/ai-services/openai/how-to/create-resource", reads=["az provider show"])
def provider(ctx, c):
    state = ctx.az(["provider", "show", "-n", "Microsoft.CognitiveServices", "--query", "registrationState"])
    if state is None:
        return c.warn("couldn't read Microsoft.CognitiveServices")
    if state == "Registered":
        return c.ok("Microsoft.CognitiveServices is registered")
    return c.fail(f"Microsoft.CognitiveServices is {state}", "az provider register -n Microsoft.CognitiveServices")


@check("ai.models", "Copilot model", needs="Reader on the subscription", kb=KB, features=["ai"],
       inputs=["location", "ai_model"], source="https://learn.microsoft.com/azure/ai-services/openai/concepts/models",
       reads=["az cognitiveservices model list"])
def models(ctx, c):
    """The model Nerdio's Copilot deploys, offered in the region as Global or Data Zone Standard.
    Nerdio's docs name the model; it's an input (ai_model) rather than a guess."""
    location, model = ctx.values["location"], ctx.values["ai_model"]
    rows = ctx.az(["cognitiveservices", "model", "list", "-l", location,
                   "--query", f"[?model.name=='{model}'].model.skus[].name"])
    if rows is None:
        return c.warn(f"couldn't list Azure OpenAI models in {location}")
    offered = sorted(set(rows) & set(DEPLOY_TYPES))
    if offered:
        return c.ok(f"{model} is offered in {location} as " + " and ".join(offered))
    return c.fail(f"{model} isn't offered in {location} as Global or Data Zone Standard",
                  f"az cognitiveservices model list -l <region> --query \"[?model.name=='{model}']\" to find a region")


@check("ai.quota", "Copilot quota", needs="Reader on the subscription", kb=KB, features=["ai"],
       inputs=["location", "ai_model"], source="https://learn.microsoft.com/azure/ai-services/openai/quotas-limits",
       reads=["az cognitiveservices usage list"])
def quota(ctx, c):
    location, model = ctx.values["location"], ctx.values["ai_model"]
    rows = ctx.az(["cognitiveservices", "usage", "list", "-l", location])
    if rows is None:
        return c.warn(f"couldn't read Azure OpenAI quota in {location}")
    found = []
    for t in DEPLOY_TYPES:
        key = f"OpenAI.{t}.{model}".lower()
        row = next((r for r in rows if (r.get("name") or {}).get("value", "").lower() == key), None)
        if row:
            found.append((t, int(row.get("limit", 0)) - int(row.get("currentValue", 0))))
    if not found:
        return c.warn(f"no quota row for {model} in {location}")
    best = max(found, key=lambda x: x[1])
    if best[1] > 0:
        return c.ok(f"{model}: {best[1]} tokens per minute (thousands) free as {best[0]} in {location}")
    return c.fail(f"{model}: no free quota in {location}",
                  f"There's no API for this: request quota with Microsoft's form ({QUOTA_FORM})")


@check("ai.copilot", "Copilot deployed", needs="Reader on the AI resource group", kb=KB, features=["ai"],
       stages=["post-wizard"], inputs=["ai_resource_group"],
       source="https://nmehelp.getnerdio.com/hc/en-us/articles/30352365570957",
       reads=["az cognitiveservices account list"])
def copilot(ctx, c):
    """Whether Nerdio has deployed Copilot's Azure OpenAI resource into the kit's AI group. Turning
    Copilot on is a Nerdio console step with no API, so a missing resource is manual, not a failure."""
    group = ctx.values["ai_resource_group"]
    rows = ctx.az(["cognitiveservices", "account", "list", "-g", group, "--query", "[].kind"])
    if rows is None:
        return c.warn(f"couldn't list Azure AI resources in {group}")
    if any(k in ("OpenAI", "AIServices") for k in rows):
        return c.ok(f"Nerdio's Azure OpenAI resource is in {group}")
    return c.manual(f"Copilot isn't turned on yet: nothing in {group}",
                    "In Nerdio Manager: System > Settings > Nerdio > Nerdio Manager Copilot > Enabled; pick "
                    f"resource group {group}, your model and deployment type, then OK")
