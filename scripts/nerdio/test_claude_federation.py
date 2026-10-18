"""Tests for ./nerdio assistant --connect-claude. Run: python3 -m unittest discover -s scripts/nerdio"""

from __future__ import annotations

import io
import json
import sys
import unittest
import urllib.error
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import claude_federation as cf

FEDERATION = {
    "issuer_url": "https://login.microsoftonline.com/00000000-0000-0000-0000-000000000000/v2.0",
    "audience": "44444444-4444-4444-4444-444444444444",
    "object_id": "66666666-6666-6666-6666-666666666666",
    "tenant_id": "00000000-0000-0000-0000-000000000000",
    "connected": False,
}


class FakeAnthropic:
    """Just enough of the Admin API, keyed by method and path."""

    def __init__(self, existing: dict | None = None):
        self.state = {"workspaces": [], "federation_issuers": [], "service_accounts": [], "federation_rules": []}
        self.state.update(existing or {})
        self.calls = []

    def __call__(self, req, timeout=None):
        path = req.full_url.removeprefix(cf.API).split("?")[0]
        body = json.loads(req.data) if req.data else None
        self.calls.append((req.get_method(), path, body, req.headers.get("Authorization")))
        kind = path.split("/")[3] if path.count("/") >= 3 else ""
        if path == "/v1/organizations/me":
            out = {"id": "55555555-5555-5555-5555-555555555555"}
        elif req.get_method() == "GET":
            out = {"data": self.state[kind], "next_page": None}
        elif path.endswith("/workspaces") and kind == "service_accounts":
            out = {"type": "service_account_workspace_member", **body}
        elif path.count("/") == 3:  # create
            prefix = {"workspaces": "wrkspc", "federation_issuers": "fdis", "service_accounts": "svac",
                      "federation_rules": "fdrl"}[kind]
            out = {"id": f"{prefix}_new", **body}
            self.state[kind].append(out)
        else:  # update
            item = next(i for i in self.state[kind] if i["id"] == path.split("/")[4])
            item.update(body)
            out = item
        return io.BytesIO(json.dumps(out).encode())


class ConnectTests(unittest.TestCase):
    def test_fresh_organization_gets_least_privilege_setup(self):
        api = FakeAnthropic()
        ids = cf.connect(cf.Admin("tok", api), "nme-assistant", FEDERATION, say=lambda *_: None)
        self.assertEqual(ids, {"organization_id": "55555555-5555-5555-5555-555555555555", "federation_rule_id": "fdrl_new",
                               "service_account_id": "svac_new", "workspace_id": "wrkspc_new"})
        issuer = api.state["federation_issuers"][0]
        self.assertEqual(issuer["issuer_url"], FEDERATION["issuer_url"])
        self.assertEqual(issuer["max_jwt_lifetime_seconds"], 86400)
        account = api.state["service_accounts"][0]
        self.assertEqual(account["organization_role"], "developer")
        rule = api.state["federation_rules"][0]
        self.assertEqual(rule["match"]["claims"], {"oid": FEDERATION["object_id"], "tid": FEDERATION["tenant_id"]})
        self.assertEqual(rule["match"]["subject_prefix"], FEDERATION["object_id"])
        self.assertNotIn("*", rule["match"]["subject_prefix"])
        self.assertEqual(rule["match"]["audience"], FEDERATION["audience"])
        self.assertEqual(rule["oauth_scope"], "workspace:inference")
        self.assertEqual(rule["token_lifetime_seconds"], 600)
        member = next(c for c in api.calls if c[1].endswith("/svac_new/workspaces"))
        self.assertEqual(member[2], {"workspace_id": "wrkspc_new", "workspace_role": "workspace_user"})
        self.assertTrue(all(c[3] == "Bearer tok" for c in api.calls))

    def test_rerun_reuses_and_repoints_the_rule(self):
        api = FakeAnthropic()
        cf.connect(cf.Admin("tok", api), "nme-assistant", FEDERATION, say=lambda *_: None)
        creates = sum(1 for m, p, *_ in api.calls if m == "POST" and p.count("/") == 3)
        new_identity = dict(FEDERATION, object_id="77777777-7777-7777-7777-777777777777")
        api.calls.clear()
        ids = cf.connect(cf.Admin("tok", api), "nme-assistant", new_identity, say=lambda *_: None)
        self.assertEqual(ids["federation_rule_id"], "fdrl_new")
        self.assertEqual(creates, 4)
        self.assertFalse([p for m, p, *_ in api.calls if m == "POST" and p.count("/") == 3])
        self.assertEqual(api.state["federation_rules"][0]["match"]["claims"]["oid"], "77777777-7777-7777-7777-777777777777")

    def test_old_issuer_lifetime_is_raised(self):
        api = FakeAnthropic({"federation_issuers": [{"id": "fdis_old", "issuer_url": FEDERATION["issuer_url"],
                                                     "max_jwt_lifetime_seconds": 7500}]})
        cf.connect(cf.Admin("tok", api), "nme-assistant", FEDERATION, say=lambda *_: None)
        self.assertEqual(api.state["federation_issuers"][0]["max_jwt_lifetime_seconds"], 86400)

    def test_errors_never_echo_the_token(self):
        def denied(req, timeout=None):
            raise urllib.error.HTTPError(req.full_url, 401, "Unauthorized", {}, io.BytesIO(b'{"error":{"message":"bad"}}'))
        with self.assertRaises(cf.FederationError) as err:
            cf.Admin("sk-ant-oat01-secret", denied).call("GET", "/v1/organizations/me")
        self.assertNotIn("secret", str(err.exception))
        self.assertIn("ant auth login", str(err.exception))


class HelperTests(unittest.TestCase):
    def test_parse_ids(self):
        self.assertEqual(cf.parse_ids("org=o,rule=fdrl_1,account=svac_1"),
                         {"organization_id": "o", "federation_rule_id": "fdrl_1", "service_account_id": "svac_1"})
        with self.assertRaises(cf.FederationError):
            cf.parse_ids("rule=fdrl_1")
        with self.assertRaises(cf.FederationError):
            cf.parse_ids("org=o,rule=fdrl_1,account=svac_1,key=sk-ant")

    def test_console_steps_name_every_value(self):
        text = cf.console_steps("nme-assistant", FEDERATION)
        for value in (FEDERATION["issuer_url"], FEDERATION["audience"], FEDERATION["object_id"], "86400", "workspace:inference"):
            self.assertIn(value, text)


if __name__ == "__main__":
    unittest.main()
