"""Azure OpenAI for the setup chat, for tenants where Claude isn't offered (Azure Government).

Decision 0036: in Azure Government the chat calls an Azure OpenAI deployment in the same tenant
and a Government region, signed in with the app's managed identity. No API key exists: the resource
has local auth turned off, and the identity holds only Cognitive Services OpenAI User on it.

The agent loop (agent.py) speaks the Claude Messages API: tool_use and tool_result blocks,
stop_reason and usage. This module is a thin adapter so the loop, the tools and the transcript the
browser keeps stay exactly the same whichever model answers. It translates one request to Azure
OpenAI's Chat Completions API and the reply back, with the standard library only (no new
dependency in the image).
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request

DEFAULT_API_VERSION = "2024-10-21"  # Chat Completions GA; override with NERDIO_AOAI_API_VERSION
TIMEOUT = 300

# finish_reason -> the stop_reason agent.chat_turn understands
STOP_REASONS = {"stop": "end_turn", "tool_calls": "tool_use", "function_call": "tool_use",
                "length": "max_tokens", "content_filter": "refusal"}


class AzureOpenAIError(RuntimeError):
    """The model call failed. The message carries the HTTP status and Azure's error code only."""


class Block(dict):
    """A content block shaped like the Anthropic SDK's, so agent.py can model_dump() it."""

    def model_dump(self, mode: str = "json", exclude_none: bool = False) -> dict:
        return {k: v for k, v in self.items() if not (exclude_none and v is None)}


class Usage:
    def __init__(self, raw: dict | None):
        raw = raw or {}
        cached = (raw.get("prompt_tokens_details") or {}).get("cached_tokens") or 0
        # Claude counts cache reads apart from input; do the same so the usage log adds up alike.
        self.input_tokens = max((raw.get("prompt_tokens") or 0) - cached, 0)
        self.output_tokens = raw.get("completion_tokens") or 0
        self.cache_read_input_tokens = cached
        self.cache_creation_input_tokens = 0


class Response:
    def __init__(self, content: list, stop_reason: str, usage: Usage, model: str | None):
        self.content = content
        self.stop_reason = stop_reason
        self.usage = usage
        self.model = model


def _text(content) -> str:
    if isinstance(content, str):
        return content
    return "\n\n".join(b.get("text", "") for b in content or [] if isinstance(b, dict) and b.get("type") == "text")


def _tool_result_text(content) -> str:
    return content if isinstance(content, str) else _text(content)


def to_chat_messages(system, messages: list) -> list:
    """Claude-style system and transcript -> Chat Completions messages."""
    out = []
    system_text = _text(system)
    if system_text:
        out.append({"role": "system", "content": system_text})
    for msg in messages:
        role, content = msg.get("role"), msg.get("content")
        if role == "assistant":
            blocks = [{"type": "text", "text": content}] if isinstance(content, str) else (content or [])
            item = {"role": "assistant", "content": _text(blocks) or None}
            calls = [{"id": b["id"], "type": "function",
                      "function": {"name": b["name"], "arguments": json.dumps(b.get("input") or {})}}
                     for b in blocks if b.get("type") == "tool_use"]
            if calls:
                item["tool_calls"] = calls
            out.append(item)
            continue
        if isinstance(content, str):
            out.append({"role": "user", "content": content})
            continue
        # A user turn: tool results become tool messages (they must follow the assistant's calls
        # directly), any text after them a user message.
        text = []
        for b in content or []:
            if b.get("type") == "tool_result":
                out.append({"role": "tool", "tool_call_id": b["tool_use_id"],
                            "content": _tool_result_text(b.get("content"))})
            elif b.get("type") == "text":
                text.append(b.get("text", ""))
        if text:
            out.append({"role": "user", "content": "\n\n".join(text)})
    return out


def to_chat_tools(tools: list) -> list:
    # Claude's strict flag isn't carried over: OpenAI's strict mode needs every property required,
    # and some of the kit's tools have optional ones. The tools validate their own input anyway.
    return [{"type": "function", "function": {"name": t["name"], "description": t.get("description", ""),
                                              "parameters": t["input_schema"]}} for t in tools]


def from_chat_response(body: dict) -> Response:
    choice = (body.get("choices") or [{}])[0]
    message = choice.get("message") or {}
    content = []
    if message.get("content"):
        content.append(Block(type="text", text=message["content"]))
    for call in message.get("tool_calls") or []:
        fn = call.get("function") or {}
        try:
            args = json.loads(fn.get("arguments") or "{}")
        except ValueError:
            args = {}  # the tool then reports the missing input as an error the model can fix
        content.append(Block(type="tool_use", id=call.get("id"), name=fn.get("name"),
                             input=args if isinstance(args, dict) else {}))
    finish = choice.get("finish_reason") or "stop"
    stop = STOP_REASONS.get(finish, "end_turn")
    if message.get("refusal") and not content:
        content.append(Block(type="text", text=message["refusal"]))
        stop = "refusal"
    if any(b["type"] == "tool_use" for b in content) and stop == "end_turn":
        stop = "tool_use"
    return Response(content, stop, Usage(body.get("usage")), body.get("model"))


class _Messages:
    def __init__(self, client: "AzureOpenAIClient"):
        self._client = client

    def create(self, *, model: str, max_tokens: int, messages: list, system=None, tools=None, **_ignored):
        """Same call shape as anthropic's messages.create. Claude-only options (output_config,
        cache_control) are dropped: Azure OpenAI caches long prompts on its own."""
        return self._client.complete(model, max_tokens, system, messages, tools or [])


class AzureOpenAIClient:
    """Calls one Azure OpenAI deployment with an Entra token from the app's managed identity."""

    def __init__(self, endpoint: str, token_provider, api_version: str = DEFAULT_API_VERSION,
                 reasoning_effort: str = "", opener=None):
        if not endpoint.startswith("https://"):
            raise ValueError("the Azure OpenAI endpoint must be an https URL")
        self.endpoint = endpoint.rstrip("/")
        self.token_provider = token_provider
        self.api_version = api_version or DEFAULT_API_VERSION
        self.reasoning_effort = reasoning_effort
        self.opener = opener or urllib.request.urlopen
        self.messages = _Messages(self)

    def request_body(self, max_tokens: int, system, messages: list, tools: list) -> dict:
        body = {"messages": to_chat_messages(system, messages)}
        if tools:
            body["tools"] = to_chat_tools(tools)
        if self.reasoning_effort:
            # Reasoning models (o-series, gpt-5.x) take max_completion_tokens and an effort level.
            body["max_completion_tokens"] = max_tokens
            body["reasoning_effort"] = self.reasoning_effort
        else:
            body["max_tokens"] = max_tokens
        return body

    def complete(self, deployment: str, max_tokens: int, system, messages: list, tools: list) -> Response:
        url = (f"{self.endpoint}/openai/deployments/{urllib.request.quote(deployment, safe='')}"
               f"/chat/completions?api-version={urllib.request.quote(self.api_version, safe='-')}")
        data = json.dumps(self.request_body(max_tokens, system, messages, tools)).encode()
        req = urllib.request.Request(url, data=data, method="POST", headers={
            "Content-Type": "application/json", "Authorization": f"Bearer {self.token_provider()}"})
        try:
            with self.opener(req, timeout=TIMEOUT) as resp:
                return from_chat_response(json.loads(resp.read().decode("utf-8")))
        except urllib.error.HTTPError as exc:
            code = ""
            try:
                code = (json.loads(exc.read().decode("utf-8")).get("error") or {}).get("code") or ""
            except (ValueError, AttributeError):
                pass
            # Status and Azure's error code only: the body can echo the prompt.
            raise AzureOpenAIError(f"Azure OpenAI returned HTTP {exc.code}{' ' + code if code else ''}") from None
