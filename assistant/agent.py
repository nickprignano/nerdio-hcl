"""The setup chatbot's agent loop and tools.

The tools wrap the same ./nerdio engine the command line and the Actions form use, so all three
ask the same questions and apply the same rules. None of them can change Azure. Without the deploy
pipeline, anything that has to run in the tenant comes back as a Cloud Shell command to paste.
With it (pipeline.py, decision 0016), the bot can also save the answers, start a plan and read it
back; an apply still waits for a reviewer's approval in GitHub.

The server keeps no state. The browser sends the transcript and the answers with every turn,
so the app can scale to zero, and the transcript is only ever appended to.
"""

from __future__ import annotations

import json
import logging
import os
import shlex
import sys
import time
import uuid
from pathlib import Path

ROOT = Path(os.environ.get("NERDIO_KIT_ROOT", Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(ROOT / "scripts" / "nerdio"))

import engine  # noqa: E402
import nerdio  # noqa: E402
import tfcheck  # noqa: E402
from pipeline import Pipeline, PipelineError  # noqa: E402

PROMPT = (Path(__file__).resolve().parent / "prompt.md").read_text(encoding="utf-8")
PROVIDER = os.environ.get("NERDIO_MODEL_PROVIDER", "foundry")
MODEL = os.environ.get("NERDIO_MODEL", "claude-opus-5-5")  # the Foundry deployment name, or the Claude API model
EFFORT = os.environ.get("NERDIO_EFFORT", "medium")
REPO_URL = os.environ.get("NERDIO_KIT_REPO", "https://github.com/nickprignano/nerdio-hcl")
MAX_STEPS = 12
KB_ALLOWED = [ROOT / "docs" / "knowledge", ROOT / "docs" / "deployment-runbook.md", ROOT / "docs" / "setup.md",
              ROOT / "docs" / "pipeline.md"]
KB_MAX_CHARS = 40_000

# One JSON line per model call on stdout, which Container Apps sends to Log Analytics. Counts and
# timings only: no prompt, transcript, answers or credentials (decision 0022's pilot measures).
usage_log = logging.getLogger("nerdio-assistant.usage")
if not usage_log.handlers:
    _handler = logging.StreamHandler(sys.stdout)
    _handler.setFormatter(logging.Formatter("%(message)s"))
    usage_log.addHandler(_handler)
    usage_log.setLevel(logging.INFO)
    usage_log.propagate = False

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
                       "(for example docs/knowledge/nerdio/platform.md), docs/deployment-runbook.md, docs/setup.md or docs/pipeline.md. "
                       "An anchor after # is ignored. Pass docs/knowledge/README.md for the index, and "
                       "docs/knowledge/troubleshooting/known-errors.yaml for known errors and their fixes.",
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

# Offered only when the app is connected to the deploy pipeline.
PIPELINE_TOOLS = [
    {
        "name": "pipeline_save_answers",
        "description": "Save the current answers as the ones the deploy pipeline plans from, replacing what was "
                       "saved before (the old version is kept). Only after the user said yes to saving them. "
                       "\"me\" is saved as the signed-in user.",
        "input_schema": {"type": "object", "properties": {}, "additionalProperties": False},
    },
    {
        "name": "pipeline_start",
        "description": "Start the deploy workflow for one stage: platform (Azure, Entra and Nerdio Manager) first, "
                       "then config (Nerdio's own settings). With apply true, the run asks to apply after the "
                       "plan, but the apply waits until a reviewer approves it in GitHub; you can't approve it. "
                       "Stage preflight runs the read-only readiness check from the saved answers instead "
                       "(apply must be false). Only after the user said yes to this exact stage and apply choice.",
        "input_schema": {
            "type": "object",
            "properties": {"stage": {"type": "string", "enum": ["platform", "config", "preflight"]}, "apply": {"type": "boolean"}},
            "required": ["stage", "apply"],
            "additionalProperties": False,
        },
        "strict": True,
    },
    {
        "name": "pipeline_runs",
        "description": "The latest deploy runs: title (stage, plan or plan+apply), status, each job's status, "
                       "whether it's waiting for a reviewer's approval, and its link.",
        "input_schema": {"type": "object", "properties": {}, "additionalProperties": False},
    },
    {
        "name": "pipeline_plan",
        "description": "One run's result. preflight: the verdict and each readiness check's id, status, title, detail, fix, KB page and the right it needs. platform or "
                       "config: the plan's change list (each resource address and what happens to it: create, "
                       "update, delete, or delete then create), the variables adopted from an earlier Cloud Shell "
                       "run, and, once applied, the apply's result; after a platform apply that includes the names "
                       "Nerdio's setup wizard asks for. A failed run gives the error and the log's last lines, IDs masked.",
        "input_schema": {
            "type": "object",
            "properties": {
                "run_id": {"type": "integer"},
                "stage": {"type": "string", "enum": ["platform", "config", "preflight"]},
                "attempt": {"type": "integer", "description": "The run's attempt number. Default 1."},
            },
            "required": ["run_id", "stage"],
            "additionalProperties": False,
        },
    },
]


def tools_for(pipeline: Pipeline | None) -> list:
    return TOOLS + PIPELINE_TOOLS if pipeline is not None and pipeline.configured else TOOLS


class Session:
    """One turn's view of the conversation state the browser handed over."""

    def __init__(self, answers: dict | None, user_object_id: str = "", pipeline: Pipeline | None = None):
        self.schema = engine.load_schema()
        self.answers = {k: v for k, v in (answers or {}).items() if isinstance(k, str)}
        engine.ensure_seed(self.answers)
        self.user_object_id = user_object_id
        self.pipeline = pipeline if pipeline is not None and pipeline.configured else None
        self.tool_errors = 0  # tool calls that came back with an error, for the usage log

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
        # Pages, and the YAML registers next to them (known errors and their fixes).
        if not allowed or target.suffix not in (".md", ".yaml") or not target.is_file():
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

    def pipeline_save_answers(self) -> dict:
        resolved = engine.resolve(self.schema, self.answers, engine.read_sources(placeholders=True))
        if resolved.errors:
            return {"saved": False, "errors": resolved.errors, "note": "Fix these answers first."}
        answers = dict(self.answers)
        if "prefix" not in answers:
            # Pin the generated prefix so every run plans the same names the chat showed.
            answers["prefix"] = resolved.values.get("prefix", "")

        def me(value):
            if isinstance(value, list):
                return [me(v) for v in value]
            return self.user_object_id if isinstance(value, str) and value.lower() == "me" else value

        if any(me(v) != v for v in answers.values()) and not engine.UUID_RE.match(self.user_object_id or ""):
            return {"saved": False, "note": "An answer says \"me\", but I can't tell who's signed in. "
                                            "Use an Entra group name instead."}
        return self.pipeline.save_answers({k: me(v) for k, v in answers.items()})

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
            elif name.startswith("pipeline_") and self.pipeline is None:
                result = {"error": "This chat isn't connected to the deploy pipeline."}
            elif name == "pipeline_save_answers":
                result = self.pipeline_save_answers()
            elif name == "pipeline_start":
                result = self.pipeline.start(args["stage"], bool(args["apply"]))
            elif name == "pipeline_runs":
                result = self.pipeline.runs()
            elif name == "pipeline_plan":
                result = self.pipeline.plan(int(args["run_id"]), args["stage"], int(args.get("attempt") or 1))
            else:
                result = {"error": f"unknown tool {name}"}
        except PipelineError as exc:
            result = {"error": str(exc)}
        except (KeyError, TypeError, ValueError, engine.SchemaError) as exc:
            result = {"error": f"{type(exc).__name__}: {exc}"}
        if isinstance(result, dict) and "error" in result:
            self.tool_errors += 1
        return json.dumps(result, default=str)


def _as_text(value) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, list):
        return ",".join(str(v) for v in value)
    return "" if value is None else str(value)


class NotConnected(RuntimeError):
    """The chat is deployed but can't reach Claude yet; the message says what to run."""


FEDERATION_VARS = ("ANTHROPIC_ORGANIZATION_ID", "ANTHROPIC_FEDERATION_RULE_ID", "ANTHROPIC_SERVICE_ACCOUNT_ID")


def make_client():
    """Claude for the chat, with no stored key: Foundry or the Claude API, both via the app's managed identity."""
    if PROVIDER == "claude-api":
        return _claude_api_client()
    from anthropic import AnthropicFoundry

    resource = os.environ["NERDIO_FOUNDRY_RESOURCE"]
    if os.environ.get("ANTHROPIC_FOUNDRY_API_KEY"):  # local development only
        return AnthropicFoundry(resource=resource)
    from azure.identity import DefaultAzureCredential, get_bearer_token_provider

    provider = get_bearer_token_provider(DefaultAzureCredential(), "https://ai.azure.com/.default")
    return AnthropicFoundry(azure_ad_token_provider=provider, resource=resource)


def _claude_api_client():
    """The Claude API through workload identity federation (docs/assistant.md#claude-api).

    Entra gives the app's managed identity a token for the kit's audience app; the SDK trades it
    for a short-lived Claude API token and trades again before that expires. The rule on the
    Claude side accepts only this identity's object ID in this tenant.
    """
    from anthropic import Anthropic, WorkloadIdentityCredentials

    missing = [v for v in FEDERATION_VARS if not os.environ.get(v)]
    resource = os.environ.get("NERDIO_CLAUDE_TOKEN_RESOURCE", "")
    if missing or not resource:
        if os.environ.get("ANTHROPIC_API_KEY") and not os.environ.get("IDENTITY_ENDPOINT"):
            return Anthropic()  # local development only; never set in Azure
        raise NotConnected("The chat isn't connected to the Claude API yet. In Cloud Shell, run "
                           "./nerdio assistant --connect-claude, then reload this page.")
    # Either variable would quietly win over federation, so they never apply in Azure.
    for var in ("ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN"):
        os.environ.pop(var, None)
    from azure.identity import ManagedIdentityCredential

    identity = ManagedIdentityCredential(client_id=os.environ.get("AZURE_CLIENT_ID"))
    scope = resource.rstrip("/") + "/.default"
    return Anthropic(credentials=WorkloadIdentityCredentials(
        identity_token_provider=lambda: identity.get_token(scope).token,
        federation_rule_id=os.environ["ANTHROPIC_FEDERATION_RULE_ID"],
        organization_id=os.environ["ANTHROPIC_ORGANIZATION_ID"],
        service_account_id=os.environ["ANTHROPIC_SERVICE_ACCOUNT_ID"],
        workspace_id=os.environ.get("ANTHROPIC_WORKSPACE_ID") or None,
    ))


TOKEN_FIELDS = ("input_tokens", "output_tokens", "cache_read_input_tokens", "cache_creation_input_tokens")


def _log_usage(response, turn: str, step: int, seconds: float) -> dict:
    usage = getattr(response, "usage", None)
    record = {"event": "model_call", "turn": turn, "provider": PROVIDER, "model": MODEL,
              "served_model": getattr(response, "model", None), "effort": EFFORT, "step": step,
              "stop_reason": response.stop_reason, "latency_ms": round(seconds * 1000)}
    for field in TOKEN_FIELDS:
        record[field] = getattr(usage, field, None) or 0
    usage_log.info(json.dumps(record))
    return record


def _log_turn(turn: str, outcome: str, calls: list, tool_errors: int, seconds: float, error: str = "") -> None:
    """One line per chat turn (the pilot's task), so tokens per completed task and the failure rate add up."""
    record = {"event": "chat_turn", "turn": turn, "provider": PROVIDER, "model": MODEL, "effort": EFFORT,
              "outcome": outcome, "calls": len(calls), "tool_errors": tool_errors, "latency_ms": round(seconds * 1000)}
    for field in TOKEN_FIELDS:
        record[field] = sum(c[field] for c in calls)
    if error:
        record["error"] = error  # the exception's type name only
    usage_log.info(json.dumps(record))


def chat_turn(client, messages: list, answers: dict, text: str, user_object_id: str = "",
              pipeline: Pipeline | None = None) -> dict:
    """Run one user turn to completion. Returns the appended transcript, the answers and the reply text."""
    session = Session(answers, user_object_id, pipeline)
    messages = list(messages) + [{"role": "user", "content": text}]
    reply = ""
    turn, calls, turn_started = uuid.uuid4().hex, [], time.monotonic()
    outcome = "step_limit"
    for step in range(MAX_STEPS):
        started = time.monotonic()
        try:
            response = client.messages.create(
                model=MODEL,
                max_tokens=16000,
                system=[{"type": "text", "text": PROMPT, "cache_control": {"type": "ephemeral"}}],
                tools=tools_for(session.pipeline),
                messages=messages,
                output_config={"effort": EFFORT},
            )
        except Exception as exc:
            _log_turn(turn, "error", calls, session.tool_errors, time.monotonic() - turn_started, type(exc).__name__)
            raise
        calls.append(_log_usage(response, turn, step, time.monotonic() - started))
        content = [b.model_dump(mode="json", exclude_none=True) for b in response.content]
        messages.append({"role": "assistant", "content": content})
        reply = "\n\n".join(b["text"] for b in content if b.get("type") == "text").strip()
        if response.stop_reason == "refusal":
            reply = reply or "I can't help with that one. Try rephrasing, or ask about the setup questions."
            outcome = "refusal"
            break
        if response.stop_reason == "max_tokens":
            reply = (reply + "\n\n(That answer was cut off. Ask me to continue.)").strip()
            outcome = "max_tokens"
            break
        if response.stop_reason != "tool_use":
            outcome = "completed"
            break
        results = [{"type": "tool_result", "tool_use_id": b["id"], "content": session.run_tool(b["name"], b.get("input") or {})}
                   for b in content if b.get("type") == "tool_use"]
        messages.append({"role": "user", "content": results})
    else:
        reply = (reply + "\n\n(I stopped after too many steps. Ask me to continue.)").strip()
    _log_turn(turn, outcome, calls, session.tool_errors, time.monotonic() - turn_started)
    return {"messages": messages, "answers": session.answers, "reply": reply}
