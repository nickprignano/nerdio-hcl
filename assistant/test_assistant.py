"""Tests for the setup chatbot. Run: python3 -m unittest discover -s assistant"""

from __future__ import annotations

import json
import shlex
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from anthropic.types import Message  # noqa: E402

import agent  # noqa: E402

MAKE_CLIENT = agent.make_client  # AppTests swaps in a fake


def message(stop_reason: str, *blocks: dict) -> Message:
    return Message.model_validate({
        "id": "msg_test", "type": "message", "role": "assistant", "model": "claude-opus-5-5",
        "content": list(blocks), "stop_reason": stop_reason, "stop_sequence": None,
        "usage": {"input_tokens": 1, "output_tokens": 1},
    })


class FakeMessages:
    def __init__(self, replies):
        self.replies = list(replies)
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(json.loads(json.dumps(kwargs, default=str)))
        return self.replies.pop(0)


class FakeClient:
    def __init__(self, replies):
        self.messages = FakeMessages(replies)


class ToolTests(unittest.TestCase):
    def setUp(self):
        self.session = agent.Session({"_random4": "ab12"})

    def test_questions_carry_current_values_and_sources(self):
        out = self.session.get_questions("discover")
        ids = [q["id"] for q in out["questions"]]
        self.assertEqual(ids[:4], ["environment", "identity_model", "user_count", "workload"])
        self.assertIn("location", ids)
        self.assertNotIn("tenant_id", ids)
        identity = next(q for q in out["questions"] if q["id"] == "identity_model")
        self.assertEqual(identity["current"], "entra_joined")
        self.assertTrue(identity["kb"])

    def test_set_answers_validates_like_the_cli(self):
        out = self.session.set_answers({"user_count": 40, "workload": "heavy", "address_space": "8.8.8.0/24",
                                        "tenant_id": "x", "fslogix_enabled": False, "user_groups": ["AVD Users"]})
        self.assertEqual(self.session.answers["user_count"], 40)
        self.assertFalse(self.session.answers["fslogix_enabled"])
        self.assertNotIn("address_space", self.session.answers)
        self.assertEqual(len(out["errors"]), 2)  # public range, and tenant_id can't be set

    def test_review_uses_placeholders_and_terraform(self):
        out = self.session.review_config()
        self.assertTrue(out["ok"], out)
        self.assertEqual(out["tfvars"]["platform"]["tenant_id"], "00000000-0000-0000-0000-000000000000")
        self.assertEqual(out["tfvars"]["platform"]["prefix"], "nme-sandbox-ab12")

    def test_kb_reads_only_knowledge_pages(self):
        self.assertIn("content", self.session.read_kb("docs/knowledge/nerdio/platform.md#roles-needed"))
        self.assertIn("content", self.session.read_kb("docs/deployment-runbook.md"))
        for bad in ("../../etc/passwd", "docs/knowledge/../../README.md", "/etc/hosts", "schema/parameters.json",
                    "docs/knowledge/sources.toml"):
            self.assertIn("error", self.session.read_kb(bad), bad)

    def test_commands_quote_values_and_pin_the_prefix(self):
        self.session.set_answers({"workspace_friendly_name": "Desks; rm -rf ~", "user_count": 12})
        cmd = self.session.cloud_shell_command("init")["command"]
        self.assertIn(shlex.quote("workspace_friendly_name=Desks; rm -rf ~"), cmd)
        self.assertIn("--set prefix=nme-sandbox-ab12", cmd)
        self.assertNotIn("_random4", cmd)
        pre = self.session.cloud_shell_command("preflight")["command"]
        self.assertTrue(pre.endswith("./nerdio preflight"))

    def test_bad_tool_input_is_an_error_result_not_a_crash(self):
        self.assertIn("error", json.loads(self.session.run_tool("get_questions", {})))
        self.assertIn("error", json.loads(self.session.run_tool("nope", {})))


class LoopTests(unittest.TestCase):
    def test_tool_round_trip_then_answer(self):
        client = FakeClient([
            message("tool_use",
                    {"type": "text", "text": "Saving that."},
                    {"type": "tool_use", "id": "toolu_1", "name": "set_answers", "input": {"answers": {"user_count": 25}}}),
            message("end_turn", {"type": "text", "text": "Got it: 25 users."}),
        ])
        out = agent.chat_turn(client, [], {}, "About 25 people")
        self.assertEqual(out["reply"], "Got it: 25 users.")
        self.assertEqual(out["answers"]["user_count"], 25)
        roles = [m["role"] for m in out["messages"]]
        self.assertEqual(roles, ["user", "assistant", "user", "assistant"])
        result = out["messages"][2]["content"][0]
        self.assertEqual(result["tool_use_id"], "toolu_1")
        second_call = client.messages.calls[1]
        self.assertEqual(second_call["model"], agent.MODEL)
        self.assertEqual(second_call["output_config"], {"effort": agent.EFFORT})
        self.assertEqual(len(second_call["messages"]), 3)

    def test_each_model_call_logs_usage_but_no_content(self):
        client = FakeClient([message("end_turn", {"type": "text", "text": "secret-looking reply"})])
        with self.assertLogs("nerdio-assistant.usage", "INFO") as logs:
            agent.chat_turn(client, [], {}, "my private question")
        self.assertEqual(len(logs.records), 1)
        record = json.loads(logs.records[0].getMessage())
        self.assertEqual({k: record[k] for k in ("event", "model", "effort", "stop_reason", "input_tokens", "output_tokens")},
                         {"event": "model_call", "model": agent.MODEL, "effort": agent.EFFORT, "stop_reason": "end_turn",
                          "input_tokens": 1, "output_tokens": 1})
        self.assertEqual(record["cache_read_input_tokens"], 0)
        self.assertIsInstance(record["latency_ms"], int)
        self.assertNotIn("private", logs.output[0])
        self.assertNotIn("secret-looking", logs.output[0])

    def test_transcript_is_append_only(self):
        earlier = [{"role": "user", "content": "hi"},
                   {"role": "assistant", "content": [{"type": "text", "text": "Hello"}]}]
        client = FakeClient([message("end_turn", {"type": "text", "text": "Sure."})])
        out = agent.chat_turn(client, earlier, {"_random4": "zz99"}, "next")
        self.assertEqual(out["messages"][:2], earlier)
        self.assertEqual(out["answers"]["_random4"], "zz99")

    def test_refusal_gets_a_readable_reply(self):
        client = FakeClient([message("refusal")])
        out = agent.chat_turn(client, [], {}, "x")
        self.assertIn("can't help", out["reply"])


class AppTests(unittest.TestCase):
    def setUp(self):
        from fastapi.testclient import TestClient

        import app
        self.app = app
        app.client.cache_clear()
        app.agent.make_client = lambda: FakeClient([message("end_turn", {"type": "text", "text": "Hi there."})])
        self.http = TestClient(app.app)

    def test_page_and_security_headers(self):
        res = self.http.get("/")
        self.assertEqual(res.status_code, 200)
        self.assertIn("default-src 'self'", res.headers["content-security-policy"])
        self.assertEqual(self.http.get("/static/app.js").status_code, 200)
        self.assertEqual(self.http.get("/static/..%2Fapp.py").status_code, 404)

    def test_chat_endpoint(self):
        res = self.http.post("/api/chat", json={"text": "hello"})
        self.assertEqual(res.status_code, 200, res.text)
        self.assertEqual(res.json()["reply"], "Hi there.")

    def test_not_connected_is_a_readable_503(self):
        def not_connected():
            raise agent.NotConnected("The chat isn't connected to the Claude API yet.")
        self.app.agent.make_client = not_connected
        res = self.http.post("/api/chat", json={"text": "hello"})
        self.assertEqual(res.status_code, 503)
        self.assertIn("isn't connected", res.json()["detail"])

    def test_signed_in_name_from_easy_auth(self):
        import base64
        principal = base64.b64encode(json.dumps({"claims": [{"typ": "name", "val": "Ada Admin"}]}).encode()).decode()
        self.assertEqual(self.http.get("/api/me", headers={"x-ms-client-principal": principal}).json()["name"], "Ada Admin")


class ClaudeApiClientTests(unittest.TestCase):
    FEDERATION = {
        "ANTHROPIC_ORGANIZATION_ID": "00000000-0000-0000-0000-000000000000",
        "ANTHROPIC_FEDERATION_RULE_ID": "fdrl_test",
        "ANTHROPIC_SERVICE_ACCOUNT_ID": "svac_test",
        "NERDIO_CLAUDE_TOKEN_RESOURCE": "api://44444444-4444-4444-4444-444444444444",
        "AZURE_CLIENT_ID": "77777777-7777-7777-7777-777777777777",
        "IDENTITY_ENDPOINT": "http://localhost:42356/msi/token",
    }

    def setUp(self):
        from unittest import mock
        self.mock = mock
        self.provider = mock.patch.object(agent, "PROVIDER", "claude-api")
        self.provider.start()
        self.env = mock.patch.dict("os.environ", {}, clear=False)
        self.env.start()
        for var in list(self.FEDERATION) + ["ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN", "ANTHROPIC_WORKSPACE_ID"]:
            agent.os.environ.pop(var, None)

    def tearDown(self):
        self.env.stop()
        self.provider.stop()

    def test_unconnected_app_says_what_to_run(self):
        agent.os.environ["IDENTITY_ENDPOINT"] = "http://localhost:42356/msi/token"
        with self.assertRaises(agent.NotConnected) as err:
            MAKE_CLIENT()
        self.assertIn("--connect-claude", str(err.exception))

    def test_federation_uses_the_managed_identity_and_drops_any_key(self):
        agent.os.environ.update(self.FEDERATION, ANTHROPIC_API_KEY="sk-ant-should-not-be-used")
        token = self.mock.Mock(token="entra.jwt.token")
        with self.mock.patch("azure.identity.ManagedIdentityCredential") as cred, \
                self.mock.patch("anthropic.WorkloadIdentityCredentials") as wif, \
                self.mock.patch("anthropic.Anthropic") as client:
            cred.return_value.get_token.return_value = token
            MAKE_CLIENT()
        cred.assert_called_once_with(client_id=self.FEDERATION["AZURE_CLIENT_ID"])
        kwargs = wif.call_args.kwargs
        self.assertEqual(kwargs["federation_rule_id"], "fdrl_test")
        self.assertIsNone(kwargs["workspace_id"])
        self.assertEqual(kwargs["identity_token_provider"](), "entra.jwt.token")
        cred.return_value.get_token.assert_called_with("api://44444444-4444-4444-4444-444444444444/.default")
        self.assertEqual(client.call_args.kwargs, {"credentials": wif.return_value})
        self.assertNotIn("ANTHROPIC_API_KEY", agent.os.environ)

    def test_real_sdk_accepts_the_credentials(self):
        agent.os.environ.update(self.FEDERATION)
        with self.mock.patch("azure.identity.ManagedIdentityCredential"):
            client = MAKE_CLIENT()
        self.assertEqual(type(client).__name__, "Anthropic")


if __name__ == "__main__":
    unittest.main()
