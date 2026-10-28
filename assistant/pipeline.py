"""The chatbot's link to the deploy pipeline (decision 0016).

What the bot can do here, and nothing more:
- save the answers to answers/<env>.json in the pipeline's storage (versioned, so every change is kept)
- start the deploy workflow, as a plan, a plan that asks for an apply, or a readiness check
- read run status and each run's result: the readiness check, the plan's change summary, what a
  failure said (IDs masked), and after a platform apply the names Nerdio's wizard asks for

It can't apply anything. An apply runs only after a named reviewer approves it in GitHub, and a
GitHub App can't be a reviewer. The app's managed identity holds no Azure rights beyond these two
blob containers and signing with one Key Vault key.

GitHub access is a GitHub App installed on the kit's repository with Actions read and write,
registered from /setup/github (github_setup.py). Its private key lives in Key Vault as a
non-exportable, sign-only key tagged with the app's client ID: the bot asks Key Vault to sign a
short-lived JWT and never sees the key. Standard library only, apart from azure-identity for tokens.
"""

from __future__ import annotations

import base64
import hashlib
import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request

GITHUB_API = "https://api.github.com"
WORKFLOW = "deploy.yml"
STAGES = ("assistant", "platform", "config")
CHECKS = ("preflight", "verify")  # read-only readiness runs: before the install, and after the wizard
FIXES = ("fix-quota", "fix-vcpu")  # gated App Service quota and VM vCPU requests
RUNNABLE = STAGES + CHECKS + FIXES
TIMEOUT = 30


class PipelineError(Exception):
    """Something the user can act on, phrased for them."""


def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


class Pipeline:
    def __init__(self, env: dict | None = None, credential=None, opener=None):
        env = os.environ if env is None else env
        self.storage = env.get("NERDIO_PIPELINE_STORAGE", "")
        self.environment = env.get("NERDIO_PIPELINE_ENV", "")
        self.repository = env.get("NERDIO_GITHUB_REPO", "")
        self.key_url = env.get("NERDIO_GITHUB_KEY_URL", "").rstrip("/")
        self.branch = env.get("NERDIO_PIPELINE_BRANCH", "main")
        self._credential = credential
        self._open = opener or urllib.request.urlopen
        self._installation_token = ""

    @property
    def configured(self) -> bool:
        return all([self.storage, self.environment, self.repository, self.key_url])

    # -- plumbing ------------------------------------------------------------

    def _token(self, scope: str) -> str:
        if self._credential is None:
            from azure.identity import DefaultAzureCredential

            self._credential = DefaultAzureCredential()
        return self._credential.get_token(scope).token

    def _request(self, method: str, url: str, headers: dict, body: bytes | None = None) -> tuple[int, bytes]:
        req = urllib.request.Request(url, data=body, method=method, headers=headers)
        try:
            with self._open(req, timeout=TIMEOUT) as resp:
                return resp.status, resp.read()
        except urllib.error.HTTPError as exc:
            return exc.code, exc.read()

    def _vault_headers(self) -> dict:
        return {"Authorization": f"Bearer {self._token('https://vault.azure.net/.default')}",
                "Content-Type": "application/json"}

    def app_key(self) -> dict | None:
        """The GitHub App's key tags (client_id, app_id, slug), or None before /setup/github has run."""
        status, raw = self._request("GET", f"{self.key_url}?api-version=7.4", self._vault_headers())
        if status == 404:
            return None
        if status != 200:
            raise PipelineError(f"Couldn't read the GitHub App's key from Key Vault (HTTP {status}).")
        return json.loads(raw).get("tags") or {}

    def import_app_key(self, jwk: dict, tags: dict) -> None:
        body = {"key": jwk, "hsm": False, "attributes": {"enabled": True, "exportable": False}, "tags": tags}
        status, _ = self._request("PUT", f"{self.key_url}?api-version=7.4", self._vault_headers(),
                                  json.dumps(body).encode())
        if status != 200:
            raise PipelineError(f"Key Vault didn't accept the GitHub App's key (HTTP {status}).")

    def _github_jwt(self) -> str:
        """A ten-minute app JWT, signed by Key Vault with the non-exportable key."""
        tags = self.app_key()
        if not tags or not tags.get("client_id"):
            raise PipelineError("The chat has no GitHub App yet. Open /setup/github on this site to create one "
                                "(one click on GitHub, then install it on the repository).")
        now = int(time.time())
        header = _b64url(json.dumps({"alg": "RS256", "typ": "JWT"}).encode())
        claims = _b64url(json.dumps({"iat": now - 60, "exp": now + 540, "iss": tags["client_id"]}).encode())
        signing_input = f"{header}.{claims}".encode()
        digest = _b64url(hashlib.sha256(signing_input).digest())
        status, raw = self._request(
            "POST", f"{self.key_url}/sign?api-version=7.4", self._vault_headers(),
            json.dumps({"alg": "RS256", "value": digest}).encode())
        if status != 200:
            raise PipelineError(f"Key Vault wouldn't sign for the GitHub App (HTTP {status}).")
        return f"{header}.{claims}.{json.loads(raw)['value']}"

    def _repo_token(self) -> str:
        """An hour-long installation token, fetched once per chat turn."""
        if self._installation_token:
            return self._installation_token
        jwt_headers = {"Authorization": f"Bearer {self._github_jwt()}", "Accept": "application/vnd.github+json",
                       "X-GitHub-Api-Version": "2022-11-28"}
        status, raw = self._request("GET", f"{GITHUB_API}/repos/{self.repository}/installation", jwt_headers)
        if status != 200:
            raise PipelineError(f"The chat's GitHub App isn't installed on {self.repository}. Open /setup/github "
                                "on this site for the install link.")
        installation = json.loads(raw)["id"]
        # Scoped down to this one repository and Actions only, whatever else the app was granted.
        status, raw = self._request(
            "POST", f"{GITHUB_API}/app/installations/{installation}/access_tokens", jwt_headers,
            json.dumps({"repositories": [self.repository.split("/", 1)[1]],
                        "permissions": {"actions": "write"}}).encode())
        if status != 201:
            raise PipelineError("GitHub wouldn't issue a token for the app. Check it has Actions: read and write.")
        self._installation_token = json.loads(raw)["token"]
        return self._installation_token

    def _github(self, method: str, path: str, body: dict | None = None) -> tuple[int, dict]:
        token = self._repo_token()
        status, raw = self._request(
            method, f"{GITHUB_API}/repos/{self.repository}{path}",
            {"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json",
             "X-GitHub-Api-Version": "2022-11-28", "Content-Type": "application/json"},
            None if body is None else json.dumps(body).encode())
        return status, (json.loads(raw) if raw else {})

    def _blob_url(self, container: str, name: str) -> str:
        return f"https://{self.storage}.blob.core.windows.net/{container}/{urllib.parse.quote(name)}"

    def _blob_headers(self) -> dict:
        return {"Authorization": f"Bearer {self._token('https://storage.azure.com/.default')}",
                "x-ms-version": "2023-11-03"}

    # -- what the tools call -------------------------------------------------

    def save_answers(self, answers: dict) -> dict:
        body = (json.dumps(answers, indent=2, sort_keys=True) + "\n").encode()
        headers = {**self._blob_headers(), "x-ms-blob-type": "BlockBlob", "Content-Type": "application/json"}
        status, _ = self._request("PUT", self._blob_url("answers", f"{self.environment}.json"), headers, body)
        if status not in (200, 201):
            raise PipelineError(f"Couldn't save the answers to the pipeline's storage (HTTP {status}).")
        return {"saved": True, "environment": self.environment, "keys": sorted(answers)}

    def start(self, stage: str, apply: bool, fix_family: str = "", fix_limit: int | None = None,
              fix_contact: str = "") -> dict:
        if stage not in RUNNABLE:
            raise PipelineError(f"stage must be one of {', '.join(RUNNABLE)}")
        apply = apply and stage not in CHECKS  # the readiness check never applies
        inputs = {"environment": self.environment, "stage": stage, "apply": "true" if apply else "false"}
        if stage in FIXES:
            if fix_family:
                inputs["fix_family"] = str(fix_family)
            if fix_limit is not None:
                inputs["fix_limit"] = str(int(fix_limit))
            if fix_contact:
                inputs["fix_contact"] = str(fix_contact)
        status, data = self._github("POST", f"/actions/workflows/{WORKFLOW}/dispatches", {
            "ref": self.branch,
            "inputs": inputs,
        })
        if status not in (200, 204):
            raise PipelineError(f"GitHub didn't start the deploy workflow (HTTP {status}): {data.get('message', '')}")
        return {"started": True, "stage": stage, "apply_requested": apply, "environment": self.environment}

    def runs(self, limit: int = 5) -> dict:
        status, data = self._github("GET", f"/actions/workflows/{WORKFLOW}/runs?per_page={int(limit)}")
        if status != 200:
            raise PipelineError(f"Couldn't list deploy runs (HTTP {status}).")
        out = []
        for run in data.get("workflow_runs", []):
            item = {k: run.get(k) for k in ("id", "run_attempt", "display_title", "status", "conclusion",
                                            "created_at", "html_url")}
            _, jobs = self._github("GET", f"/actions/runs/{run['id']}/jobs")
            item["jobs"] = [{"name": j.get("name"), "status": j.get("status"), "conclusion": j.get("conclusion")}
                            for j in jobs.get("jobs", [])]
            # GitHub shows a job held by an environment's reviewers as "waiting".
            item["waiting_for_approval"] = run.get("status") == "waiting"
            out.append(item)
        return {"environment": self.environment, "runs": out}

    def _result(self, name: str) -> dict | None:
        status, raw = self._request("GET", self._blob_url("plans", name), self._blob_headers())
        if status == 404:
            return None
        if status != 200:
            raise PipelineError(f"Couldn't read the run's result (HTTP {status}).")
        return json.loads(raw)

    def plan(self, run_id: int, stage: str, attempt: int = 1) -> dict:
        """One run's result for a stage: the readiness check, or the plan and, if it ran, the apply."""
        if stage not in RUNNABLE:
            raise PipelineError(f"stage must be one of {', '.join(RUNNABLE)}")
        base = f"{self.environment}/{int(run_id)}-{int(attempt)}"
        summary = self._result(f"{base}/{stage}.json")
        if summary is None:
            return {"found": False, "note": "No result for that run yet. Its first job may still be running."}
        if summary.get("status") == "failed":
            return {"found": True, "status": "failed", "error": summary.get("error"), "log_tail": summary.get("log_tail")}
        if stage in CHECKS:
            # readiness.json results (nerdio-readiness/1): id, status, title, detail, fix, kb, needs.
            results = [r for r in summary.get("results", []) if r.get("status") != "skipped"]
            return {"found": True, "status": summary.get("status"), "verdict": summary.get("verdict"),
                    "counts": summary.get("counts", {}), "results": results}
        changes = summary.get("changes", [])
        out = {"found": True, "status": summary.get("status", "planned"), "summary": summary.get("summary"),
               "adopted": summary.get("adopted", []), "change_count": len(changes),
               "changes": changes[:300], "truncated": len(changes) > 300}
        # A re-run of only the apply job is a later attempt of the same run, so look there too.
        for later in range(int(attempt), int(attempt) + 3):
            applied = self._result(f"{self.environment}/{int(run_id)}-{later}/{stage}-apply.json")
            if applied is not None:
                out["apply"] = applied
                break
        return out
