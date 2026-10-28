"""Tests for the chatbot's deploy pipeline link. Run: python3 -m unittest discover -s assistant"""

from __future__ import annotations

import base64
import io
import json
import shutil
import subprocess
import sys
import unittest
import unittest.mock
import urllib.error
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import agent  # noqa: E402
import github_setup  # noqa: E402
from pipeline import Pipeline, PipelineError  # noqa: E402

ENV = {
    "NERDIO_PIPELINE_STORAGE": "stexampletf000000",
    "NERDIO_PIPELINE_ENV": "sandbox",
    "NERDIO_GITHUB_REPO": "contoso/nerdio-hcl",
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
    ("GET", ENV["NERDIO_GITHUB_KEY_URL"] + "?"): (200, {"tags": {"client_id": "Iv1.example", "slug": "nerdio-chat-abc123"}}),
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
        sign = http.calls[1]
        self.assertEqual(sign[2]["Authorization"], "Bearer token-for-https://vault.azure.net/.default")
        self.assertEqual(sign[3]["alg"], "RS256")
        jwt = http.calls[2][2]["Authorization"].removeprefix("Bearer ")
        claims = json.loads(base64.urlsafe_b64decode(jwt.split(".")[1] + "=="))
        self.assertEqual(claims["iss"], "Iv1.example")
        self.assertLessEqual(claims["exp"] - claims["iat"], 600)
        self.assertEqual(jwt.split(".")[2], "c2lnbmF0dXJl")
        # The installation token is cut down to this repository and Actions.
        self.assertEqual(http.calls[3][3], {"repositories": ["nerdio-hcl"], "permissions": {"actions": "write"}})
        dispatch = http.calls[4]
        self.assertEqual(dispatch[2]["Authorization"], "Bearer ghs_example")
        self.assertEqual(dispatch[3], {"ref": "main", "inputs": {"environment": "sandbox", "stage": "platform", "apply": "true"}})

    def test_rejects_unknown_stage(self):
        p, _ = pipeline({})
        with self.assertRaises(PipelineError):
            p.start("everything", False)

    def test_points_to_setup_before_the_app_exists(self):
        http = FakeHttp({("GET", ENV["NERDIO_GITHUB_KEY_URL"] + "?"): (404, {"error": {"code": "KeyNotFound"}})})
        p = Pipeline(ENV, credential=Credential(), opener=http)
        with self.assertRaisesRegex(PipelineError, "/setup/github"):
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
        no_apply = ("GET", "https://stexampletf000000.blob.core.windows.net/plans/sandbox/7-")
        p, _ = pipeline({("GET", url): (200, {"summary": "Plan: 1 to add", "adopted": ["prefix"],
                                              "changes": [{"action": "create", "address": "a.b"}]}),
                         no_apply: (404, b"")})
        out = p.plan(7, "platform")
        self.assertEqual(out["change_count"], 1)
        self.assertEqual(out["adopted"], ["prefix"])
        self.assertNotIn("apply", out)
        p, _ = pipeline({("GET", url): (404, b"")})
        self.assertFalse(p.plan(7, "platform")["found"])

    def test_plan_includes_the_apply_and_wizard_values(self):
        blobs = "https://stexampletf000000.blob.core.windows.net/plans/sandbox/"
        applied = {"status": "applied", "outputs": {"avd_vnet_name": "vnet-contoso-avd"}}
        p, http = pipeline({("GET", blobs + "7-1/platform.json"): (200, {"summary": "Plan: 1 to add", "changes": []}),
                            ("GET", blobs + "7-1/platform-apply.json"): (404, b""),
                            # Only the apply job was re-run, so its result is under the next attempt.
                            ("GET", blobs + "7-2/platform-apply.json"): (200, applied)})
        out = p.plan(7, "platform")
        self.assertEqual(out["apply"]["outputs"]["avd_vnet_name"], "vnet-contoso-avd")

    def test_failed_run_reports_the_error(self):
        url = "https://stexampletf000000.blob.core.windows.net/plans/sandbox/8-1/platform.json"
        p, _ = pipeline({("GET", url): (200, {"status": "failed", "error": "terraform plan failed",
                                              "log_tail": "Error: quota exceeded"})})
        out = p.plan(8, "platform")
        self.assertEqual(out["status"], "failed")
        self.assertIn("quota", out["log_tail"])

    def test_preflight_runs_and_never_applies(self):
        dispatch = "https://api.github.com/repos/contoso/nerdio-hcl/actions/workflows/deploy.yml/dispatches"
        p, http = pipeline({(("POST", dispatch)): (204, b"")})
        out = p.start("preflight", True)
        self.assertFalse(out["apply_requested"])
        self.assertEqual(http.calls[-1][3]["inputs"], {"environment": "sandbox", "stage": "preflight", "apply": "false"})
        url = "https://stexampletf000000.blob.core.windows.net/plans/sandbox/9-1/preflight.json"
        p, _ = pipeline({("GET", url): (200, {"status": "no-go", "verdict": "NO-GO", "results": [
            {"id": "sub.sql", "status": "fail", "title": "Azure SQL region"},
            {"id": "net.hub", "status": "skipped", "title": "Hub network"}]})})
        out = p.plan(9, "preflight")
        self.assertEqual(out["status"], "no-go")
        self.assertEqual(out["verdict"], "NO-GO")
        self.assertEqual([r["id"] for r in out["results"]], ["sub.sql"])
        with self.assertRaises(PipelineError):
            p.start("destroy", False)

    def test_verify_runs_and_never_applies(self):
        dispatch = "https://api.github.com/repos/contoso/nerdio-hcl/actions/workflows/deploy.yml/dispatches"
        p, http = pipeline({(("POST", dispatch)): (204, b"")})
        self.assertFalse(p.start("verify", True)["apply_requested"])
        self.assertEqual(http.calls[-1][3]["inputs"]["stage"], "verify")
        url = "https://stexampletf000000.blob.core.windows.net/plans/sandbox/9-1/verify.json"
        p, _ = pipeline({("GET", url): (200, {"status": "go", "verdict": "GO", "results": [
            {"id": "nme.health", "status": "pass", "title": "Health page"}]})})
        self.assertEqual(p.plan(9, "verify")["verdict"], "GO")

    def test_assistant_stage_plans_and_applies(self):
        dispatch = "https://api.github.com/repos/contoso/nerdio-hcl/actions/workflows/deploy.yml/dispatches"
        p, http = pipeline({(("POST", dispatch)): (204, b"")})
        out = p.start("assistant", True)
        self.assertTrue(out["apply_requested"])
        self.assertEqual(http.calls[-1][3]["inputs"], {"environment": "sandbox", "stage": "assistant", "apply": "true"})
        blobs = "https://stexampletf000000.blob.core.windows.net/plans/sandbox/"
        p, _ = pipeline({
            ("GET", blobs + "10-1/assistant.json"): (200, {"summary": "Plan: 0 to add, 1 to change", "changes": [
                {"action": "update", "address": "module.assistant.azurerm_container_app.this"}]}),
            ("GET", blobs + "10-1/assistant-apply.json"): (200, {"status": "applied", "outputs": {"url": "https://ca-nme-assistant.example.azurecontainerapps.io"}}),
        })
        plan_out = p.plan(10, "assistant")
        self.assertEqual(plan_out["change_count"], 1)
        self.assertEqual(plan_out["apply"]["outputs"]["url"], "https://ca-nme-assistant.example.azurecontainerapps.io")

    def test_fix_quota_and_vcpu_stages_pass_optional_inputs(self):
        dispatch = "https://api.github.com/repos/contoso/nerdio-hcl/actions/workflows/deploy.yml/dispatches"
        p, http = pipeline({(("POST", dispatch)): (204, b"")})
        out = p.start("fix-vcpu", True, fix_family="standardDSv5Family", fix_limit=48)
        self.assertTrue(out["apply_requested"])
        self.assertEqual(http.calls[-1][3]["inputs"], {
            "environment": "sandbox",
            "stage": "fix-vcpu",
            "apply": "true",
            "fix_family": "standardDSv5Family",
            "fix_limit": "48",
        })
        p.start("fix-quota", False, fix_limit=2, fix_contact="admin@contoso.com,USA")
        self.assertEqual(http.calls[-1][3]["inputs"], {
            "environment": "sandbox",
            "stage": "fix-quota",
            "apply": "false",
            "fix_limit": "2",
            "fix_contact": "admin@contoso.com,USA",
        })
        blobs = "https://stexampletf000000.blob.core.windows.net/plans/sandbox/"
        p, _ = pipeline({
            ("GET", blobs + "11-1/fix-vcpu.json"): (200, {
                "summary": "Raise standardDSv5Family vCPU quota in eastus2 from 10 to 48 (Azure Quota API).",
                "changes": [{"action": "request", "address": "quota.vcpu"}],
            }),
            ("GET", blobs + "11-1/fix-vcpu-apply.json"): (200, {
                "status": "applied",
                "outputs": {"detail": "Requested."},
            }),
        })
        plan_out = p.plan(11, "fix-vcpu")
        self.assertEqual(plan_out["changes"], [{"action": "request", "address": "quota.vcpu"}])
        self.assertEqual(plan_out["apply"]["status"], "applied")

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



class GitHubSetupTests(unittest.TestCase):
    def test_manifest_asks_for_actions_only_and_no_webhook(self):
        m = github_setup.manifest(Pipeline(ENV), "https://chat.example")
        self.assertEqual(m["default_permissions"], {"actions": "write", "metadata": "read"})
        self.assertFalse(m["public"])
        self.assertFalse(m["hook_attributes"]["active"])
        self.assertEqual(m["redirect_url"], "https://chat.example/setup/github/callback")

    @unittest.skipUnless(shutil.which("openssl"), "needs openssl to make a test key")
    def test_pem_becomes_a_valid_sign_only_jwk(self):
        for args in (["genrsa", "2048"], ["genpkey", "-algorithm", "RSA", "-pkeyopt", "rsa_keygen_bits:2048"]):
            pem = subprocess.run(["openssl", *args], capture_output=True, text=True, check=True).stdout
            jwk = github_setup.pem_to_jwk(pem)
            num = {k: int.from_bytes(base64.urlsafe_b64decode(v + "=="), "big") for k, v in jwk.items()
                   if k not in ("kty", "key_ops")}
            self.assertEqual(jwk["key_ops"], ["sign"])
            self.assertEqual(num["p"] * num["q"], num["n"])
            self.assertEqual(num["e"], 65537)
            self.assertEqual((num["e"] * num["dp"]) % (num["p"] - 1), 1)

    def test_conversion_imports_the_key_and_drops_secrets(self):
        pem = "-----BEGIN RSA PRIVATE KEY-----\nMA==\n-----END RSA PRIVATE KEY-----"
        http = FakeHttp({
            ("POST", "https://api.github.com/app-manifests/abc12345/conversions"): (201, {
                "id": 9, "slug": "nerdio-chat-abc123", "client_id": "Iv1.example", "pem": pem,
                "client_secret": "SECRET-ONE", "webhook_secret": "SECRET-TWO"}),
            ("PUT", ENV["NERDIO_GITHUB_KEY_URL"] + "?"): (200, {}),
        })
        p = Pipeline(ENV, credential=Credential(), opener=http)
        jwk = {"kty": "RSA", "key_ops": ["sign"], "n": "AQ", "e": "AQAB"}
        with unittest.mock.patch.object(github_setup, "pem_to_jwk", return_value=jwk) as convert:
            out = github_setup.convert_and_import(p, "abc12345")
        convert.assert_called_once_with(pem)
        self.assertEqual(out["install_url"], "https://github.com/apps/nerdio-chat-abc123/installations/new")
        body = http.calls[1][3]
        self.assertFalse(body["attributes"]["exportable"])
        self.assertEqual(body["tags"], {"client_id": "Iv1.example", "app_id": "9", "slug": "nerdio-chat-abc123"})
        self.assertNotIn("SECRET", json.dumps(body))

    def test_rejects_odd_codes(self):
        with self.assertRaises(PipelineError):
            github_setup.convert_and_import(Pipeline(ENV), "../../evil")

    def test_callback_needs_this_browsers_state(self):
        from fastapi.testclient import TestClient

        import app as web

        client = TestClient(web.app)
        r = client.get("/setup/github/callback?code=abc12345&state=forged")
        self.assertEqual(r.status_code, 400)
        self.assertIn("Start again", r.text)


if __name__ == "__main__":
    unittest.main()
