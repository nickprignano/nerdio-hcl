"""The setup chatbot's agent loop and tools.

The tools wrap the same ./nerdio engine the command line and the Actions form use, so all three
ask the same questions and apply the same rules. None of them can reach Azure: anything that
has to run in the tenant comes back as a Cloud Shell command for the person to paste.

The server keeps no state. The browser sends the transcript and the answers with every turn,
so the app can scale to zero, and the transcript is only ever appended to.
"""

from __future__ import annotations

import json
import os
import shlex
import sys
from pathlib import Path

ROOT = Path(os.environ.get("NERDIO_KIT_ROOT", Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(ROOT / "scripts" / "nerdio"))

import engine  # noqa: E402
import nerdio  # noqa: E402
import tfcheck  # noqa: E402

PROMPT = (Path(__file__).resolve().parent / "prompt.md").read_text(encoding="utf-8")
MODEL = os.environ.get("NERDIO_MODEL", "claude-opus-5-5")  # the Foundry deployment name
EFFORT = os.environ.get("NERDIO_EFFORT", "medium")
REPO_URL = os.environ.get("NERDIO_KIT_REPO", "https://github.com/nickprignano/nerdio-hcl")
MAX_STEPS = 12
KB_ALLOWED = [ROOT / "docs" / "knowledge", ROOT / "docs" / "deployment-runbook.md", ROOT / "docs" / "setup.md"]
KB_MAX_CHARS = 40_000

TOOLS = [
    {
        "name": "get_questions",
        "description": "The kit's setup questions for one phase, with help text, choices, validation, "
                       "knowledge-base links and each question's current value (an earlier answer or the default).",
        "input_schema": {
            "type": "object",
            "properties": {
                "phase": {"type": "string", "enum": ["discover", "configure"]},
                "advanced": {"type": "boolean", "description": "Include advanced questions. Default false."},
            },
            "required": ["phase"],
            "additionalProperties": False,
        },
        "strict": True,
    },
    {
        "name": "set_answers",
        "description": "Record the user's answers, keyed by question id. Values are validated against the schema; "
                       "rejected values come back in `errors` with the reason and are not saved. An empty string "
                       "resets a question to its default. Lists can be arrays or comma-separated strings.",
        "input_schema": {
            "type": "object",
            "properties": {"answers": {"type": "object", "additionalProperties": True}},
            "required": ["answers"],
        },
    },
    {
        "name": "review_config",
        "description": "Render the configuration the current answers produce, as the two tfvars files, with "
                       "placeholder IDs, and have Terraform check it against the kit's variables.",
        "input_schema": {"type": "object", "properties": {}, "additionalProperties": False},
    },
    {
        "name": "read_kb",
        "description": "Read a page of the kit's knowledge base to ground an answer: a path under docs/knowledge/ "
                       "(for example docs/knowledge/nerdio/platform.md), docs/deployment-runbook.md or docs/setup.md. "
                       "An anchor after # is ignored. Pass docs/knowledge/README.md for the index.",
        "input_schema": {
            "type": "object",
            "properties": {"path": {"type": "string"}},
            "required": ["path"],
            "additionalProperties": False,
        },
        "strict": True,
    },
    {
        "name": "cloud_shell_command",
        "description": "Build the one command the user pastes into Azure Cloud Shell (Bash). `preflight` runs the "
                       "read-only readiness checks for the current answers. `init` writes the configuration files "
                       "after Terraform checks them.",
        "input_schema": {
            "type": "object",
            "properties": {"kind": {"type": "string", "enum": ["preflight", "init"]}},
            "required": ["kind"],
            "additionalProperties": False,
        },
        "strict": True,
    },
]


class Session:
    """One turn's view of the conversation state the browser handed over."""

    def __init__(self, answers: dict | None):
        self.schema = engine.load_schema()
        self.answers = {k: v for k, v in (answers or {}).items() if isinstance(k, str)}
        engine.ensure_seed(self.answers)

    # -- tools ---------------------------------------------------------------

    def get_questions(self, phase: str, advanced: bool = False) -> dict:
        resolved = engine.resolve(self.schema, self.answers, engine.read_sources(placeholders=True))
        out = []
        for p in self.schema["parameters"]:
            if p["phase"] != phase or p["id"] not in resolved.active or not nerdio.askable(p, advanced):
                continue
            item = {k: p[k] for k in ("id", "type", "question", "help", "choices", "pattern", "min", "max",
                                      "kb", "sources") if k in p}
            item["advanced"] = p.get("ask") == "advanced"
            item["current"] = resolved.values.get(p["id"])
            item["answered"] = p["id"] in self.answers
            if p["id"] in resolved.errors:
                item["error"] = resolved.errors[p["id"]]
            out.append(item)
        return {"phase": phase, "questions": out}

    def set_answers(self, answers: dict) -> dict:
        sets = [f"{k}={_as_text(v)}" for k, v in answers.items()]
        before = dict(self.answers)
        errors = nerdio.apply_sets(self.schema, self.answers, sets)
        changed = sorted(k for k in set(before) | set(self.answers) if before.get(k) != self.answers.get(k))
        resolved = engine.resolve(self.schema, self.answers, engine.read_sources(placeholders=True))
        return {"saved": changed, "errors": errors,
                "still_invalid": {k: v for k, v in resolved.errors.items() if k in resolved.active}}

    def review_config(self) -> dict:
        resolved = engine.resolve(self.schema, self.answers, engine.read_sources(placeholders=True))
        if resolved.errors:
            return {"ok": False, "errors": resolved.errors}
        rendered, problems = engine.render(self.schema, resolved, placeholders=True)
        checks = []
        for stage, tfvars in rendered.items():
            good, message = tfcheck.check_stage(engine.stage_dir(self.schema, stage, "example"), tfvars)
            checks.append({"ok": good, "message": message})
        groups = {k: self.answers[k] for k in ("user_groups", "admin_groups", "nerdio_admins") if k in self.answers}
        return {"ok": not problems and all(c["ok"] for c in checks), "terraform": checks, "problems": problems,
                "note": "IDs are placeholders; Cloud Shell fills in the tenant, subscription and group IDs.",
                "group_names": groups, "tfvars": rendered}

    def read_kb(self, path: str) -> dict:
        rel = path.split("#", 1)[0].strip().lstrip("/")
        target = (ROOT / rel).resolve()
        allowed = any(target == a.resolve() or a.resolve() in target.parents for a in KB_ALLOWED)
        if not allowed or target.suffix != ".md" or not target.is_file():
            return {"error": f"not a knowledge-base page: {path}"}
        text = target.read_text(encoding="utf-8")
        return {"path": rel, "content": text[:KB_MAX_CHARS], "truncated": len(text) > KB_MAX_CHARS}

    def cloud_shell_command(self, kind: str) -> dict:
        values = dict(self.answers)
        if "prefix" not in values:
            # Pin the generated prefix so Cloud Shell writes the same names the chat showed.
            resolved = engine.resolve(self.schema, self.answers, engine.read_sources(placeholders=True))
            values["prefix"] = resolved.values.get("prefix", "")
        sets = " ".join(f"--set {shlex.quote(f'{k}={_as_text(v)}')}"
                        for k, v in sorted(values.items()) if not k.startswith("_"))
        fetch = (f"{{ [ -d ~/nerdio-hcl ] || git clone -q {shlex.quote(REPO_URL)} ~/nerdio-hcl; }} && "
                 "cd ~/nerdio-hcl && git pull -q --ff-only")
        if kind == "preflight":
            cmd = f"{fetch} && ./nerdio init --phase discover --non-interactive {sets} >/dev/null && ./nerdio preflight"
            what = "Runs read-only checks. Paste the whole output back here."
        else:
            cmd = f"{fetch} && ./nerdio init --non-interactive {sets}"
            what = "Writes setup.auto.tfvars.json in both stages after Terraform checks them. Paste the output back here."
        return {"command": cmd, "explain": what}

    # -- dispatch ------------------------------------------------------------

    def run_tool(self, name: str, args: dict) -> str:
        try:
            if name == "get_questions":
                result = self.get_questions(args["phase"], bool(args.get("advanced", False)))
            elif name == "set_answers":
                result = self.set_answers(args.get("answers") or {})
            elif name == "review_config":
                result = self.review_config()
            elif name == "read_kb":
                result = self.read_kb(str(args["path"]))
            elif name == "cloud_shell_command":
                result = self.cloud_shell_command(args["kind"])
            else:
                result = {"error": f"unknown tool {name}"}
        except (KeyError, TypeError, ValueError, engine.SchemaError) as exc:
            result = {"error": f"{type(exc).__name__}: {exc}"}
        return json.dumps(result, default=str)


def _as_text(value) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, list):
        return ",".join(str(v) for v in value)
    return "" if value is None else str(value)


def make_client():
    """Claude on Microsoft Foundry. The app's managed identity gets a token; no API key is stored."""
    from anthropic import AnthropicFoundry

    resource = os.environ["NERDIO_FOUNDRY_RESOURCE"]
    if os.environ.get("ANTHROPIC_FOUNDRY_API_KEY"):  # local development only
        return AnthropicFoundry(resource=resource)
    from azure.identity import DefaultAzureCredential, get_bearer_token_provider

    provider = get_bearer_token_provider(DefaultAzureCredential(), "https://ai.azure.com/.default")
    return AnthropicFoundry(azure_ad_token_provider=provider, resource=resource)


def chat_turn(client, messages: list, answers: dict, text: str) -> dict:
    """Run one user turn to completion. Returns the appended transcript, the answers and the reply text."""
    session = Session(answers)
    messages = list(messages) + [{"role": "user", "content": text}]
    reply = ""
    for _ in range(MAX_STEPS):
        response = client.messages.create(
            model=MODEL,
            max_tokens=16000,
            system=[{"type": "text", "text": PROMPT, "cache_control": {"type": "ephemeral"}}],
            tools=TOOLS,
            messages=messages,
            output_config={"effort": EFFORT},
        )
        content = [b.model_dump(mode="json", exclude_none=True) for b in response.content]
        messages.append({"role": "assistant", "content": content})
        reply = "\n\n".join(b["text"] for b in content if b.get("type") == "text").strip()
        if response.stop_reason == "refusal":
            reply = reply or "I can't help with that one. Try rephrasing, or ask about the setup questions."
            break
        if response.stop_reason == "max_tokens":
            reply = (reply + "\n\n(That answer was cut off. Ask me to continue.)").strip()
            break
        if response.stop_reason != "tool_use":
            break
        results = [{"type": "tool_result", "tool_use_id": b["id"], "content": session.run_tool(b["name"], b.get("input") or {})}
                   for b in content if b.get("type") == "tool_use"]
        messages.append({"role": "user", "content": results})
    else:
        reply = (reply + "\n\n(I stopped after too many steps. Ask me to continue.)").strip()
    return {"messages": messages, "answers": session.answers, "reply": reply}
