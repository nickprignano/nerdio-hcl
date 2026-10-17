"""Tests for the chatbot's deploy pipeline link. Run: python3 -m unittest discover -s assistant"""

from __future__ import annotations

import base64
import io
import json
import sys
import unittest
import urllib.error
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import agent  # noqa: E402
from pipeline import Pipeline, PipelineError  # noqa: E402

ENV = {
    "NERDIO_PIPELINE_STORAGE": "stexampletf000000",
    "NERDIO_PIPELINE_ENV": "sandbox",
    "NERDIO_GITHUB_REPO": "contoso/nerdio-hcl",
    "NERDIO_GITHUB_APP_CLIENT_ID": "Iv1.example",
    "NERDIO_GITHUB_KEY_URL": "https://kv-example.vault.azure.net/keys/github-app",
}
USER = "11111111-1111-1111-1111-111111111111"


class Token:
    def __init__(self, scope):
        self.token = f"token-for-{scope}"


class Credential:
    def get_token(self, scope):
        return Token(scope)


class Response:
    def __init__(self, status, body=b""):
        self.status, self.body = status, body

    def read(self):
        return self.body

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


class FakeHttp:
    """Answers each request by (method, URL prefix) and records it."""

    def __init__(self, routes):
        self.routes = routes
        self.calls = []

    def __call__(self, req, timeout=None):
        try:
            body = json.loads(req.data) if req.data else None
        except ValueError:
            body = req.data
        self.calls.append((req.get_method(), req.full_url, dict(req.headers), body))
        for (method, prefix), (status, payload) in self.routes.items():
            if req.get_method() == method and req.full_url.startswith(prefix):
                raw = payload if isinstance(payload, bytes) else json.dumps(payload).encode()
                if status >= 400:
                    raise urllib.error.HTTPError(req.full_url, status, "error", {}, io.BytesIO(raw))
                return Response(status, raw)
        raise AssertionError(f"unexpected request {req.get_method()} {req.full_url}")


GITHUB_AUTH = {
    ("POST", ENV["NERDIO_GITHUB_KEY_URL"] + "/sign"): (200, {"value": "c2lnbmF0dXJl"}),
    ("GET", "https://api.github.com/repos/contoso/nerdio-hcl/installation"): (200, {"id": 42}),
    ("POST", "https://api.github.com/app/installations/42/access_tokens"): (201, {"token": "ghs_example"}),
}


def pipeline(routes):
    http = FakeHttp({**GITHUB_AUTH, **routes})
    return Pipeline(ENV, credential=Credential(), opener=http), http


class PipelineTests(unittest.TestCase):
    def test_not_configured_without_settings(self):
        self.assertFalse(Pipeline({}).configured)
        self.assertTrue(Pipeline(ENV).configured)

    def test_start_signs_with_key_vault_and_dispatches_deploy_only(self):
        p, http = pipeline({("POST", "https://api.github.com/repos/contoso/nerdio-hcl/actions/workflows/deploy.yml/dispatches"): (204, b"")})
        out = p.start("platform", True)
        self.assertTrue(out["started"])
        sign = http.calls[0]
        self.assertEqual(sign[2]["Authorization"], "Bearer token-for-https://vault.azure.net/.default")
        self.assertEqual(sign[3]["alg"], "RS256")
        jwt = http.calls[1][2]["Authorization"].removeprefix("Bearer ")
        claims = json.loads(base64.urlsafe_b64decode(jwt.split(".")[1] + "=="))
        self.assertEqual(claims["iss"], "Iv1.example")
        self.assertLessEqual(claims["exp"] - claims["iat"], 600)
        self.assertEqual(jwt.split(".")[2], "c2lnbmF0dXJl")
        # The installation token is cut down to this repository and Actions.
        self.assertEqual(http.calls[2][3], {"repositories": ["nerdio-hcl"], "permissions": {"actions": "write"}})
        dispatch = http.calls[3]
        self.assertEqual(dispatch[2]["Authorization"], "Bearer ghs_example")
        self.assertEqual(dispatch[3], {"ref": "main", "inputs": {"environment": "sandbox", "stage": "platform", "apply": "true"}})

    def test_rejects_unknown_stage(self):
        p, _ = pipeline({})
        with self.assertRaises(PipelineError):
            p.start("everything", False)

    def test_key_vault_failure_is_readable(self):
        http = FakeHttp({("POST", ENV["NERDIO_GITHUB_KEY_URL"] + "/sign"): (403, {"error": "Forbidden"})})
        p = Pipeline(ENV, credential=Credential(), opener=http)
        with self.assertRaisesRegex(PipelineError, "github-app-key.sh"):
            p.runs()

    def test_save_answers_writes_the_environment_blob(self):
        p, http = pipeline({("PUT", "https://stexampletf000000.blob.core.windows.net/answers/sandbox.json"): (201, b"")})
        out = p.save_answers({"location": "centralus"})
        self.assertTrue(out["saved"])
        method, url, headers, body = http.calls[0]
        self.assertEqual(headers["X-ms-blob-type"], "BlockBlob")
        self.assertEqual(headers["Authorization"], "Bearer token-for-https://storage.azure.com/.default")
        self.assertEqual(body, {"location": "centralus"})

    def test_plan_summary(self):
        url = "https://stexampletf000000.blob.core.windows.net/plans/sandbox/7-1/platform.json"
        p, _ = pipeline({("GET", url): (200, {"summary": "Plan: 1 to add", "changes": [{"action": "create", "address": "a.b"}]})})
        out = p.plan(7, "platform")
        self.assertEqual(out["change_count"], 1)
        p, _ = pipeline({("GET", url): (404, b"")})
        self.assertFalse(p.plan(7, "platform")["found"])

    def test_runs_flag_waiting_for_approval(self):
        base = "https://api.github.com/repos/contoso/nerdio-hcl/actions"
        p, _ = pipeline({
            ("GET", f"{base}/workflows/deploy.yml/runs"): (200, {"workflow_runs": [
                {"id": 7, "run_attempt": 1, "display_title": "sandbox platform: plan and apply", "status": "waiting",
                 "conclusion": None, "created_at": "t", "html_url": "https://github.com/x"}]}),
            ("GET", f"{base}/runs/7/jobs"): (200, {"jobs": [{"name": "plan", "status": "completed", "conclusion": "success"},
                                                          {"name": "apply", "status": "waiting", "conclusion": None}]}),
        })
        run = p.runs()["runs"][0]
        self.assertTrue(run["waiting_for_approval"])
        self.assertEqual([j["name"] for j in run["jobs"]], ["plan", "apply"])


class AgentPipelineTests(unittest.TestCase):
    def test_tools_offered_only_when_connected(self):
        names = lambda tools: {t["name"] for t in tools}  # noqa: E731
        self.assertNotIn("pipeline_start", names(agent.tools_for(None)))
        self.assertNotIn("pipeline_start", names(agent.tools_for(Pipeline({}))))
        self.assertIn("pipeline_start", names(agent.tools_for(Pipeline(ENV))))

    def test_pipeline_tools_refuse_when_not_connected(self):
        session = agent.Session({"_random4": "ab12"})
        out = json.loads(session.run_tool("pipeline_start", {"stage": "platform", "apply": False}))
        self.assertIn("isn't connected", out["error"])

    def test_save_answers_resolves_me_and_pins_prefix(self):
        p, http = pipeline({("PUT", "https://stexampletf000000.blob.core.windows.net/answers/sandbox.json"): (201, b"")})
        session = agent.Session({"_random4": "ab12", "nerdio_admins": ["me", "AVD Admins"]}, USER, p)
        out = json.loads(session.run_tool("pipeline_save_answers", {}))
        self.assertTrue(out["saved"])
        saved = http.calls[0][3]
        self.assertEqual(saved["nerdio_admins"], [USER, "AVD Admins"])
        self.assertTrue(saved["prefix"])

    def test_save_answers_needs_a_signed_in_user_for_me(self):
        p, http = pipeline({})
        session = agent.Session({"_random4": "ab12", "nerdio_admins": ["me"]}, "", p)
        out = json.loads(session.run_tool("pipeline_save_answers", {}))
        self.assertFalse(out["saved"])
        self.assertEqual(http.calls, [])


if __name__ == "__main__":
    unittest.main()
