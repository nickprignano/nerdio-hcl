"""Tests for ./nerdio fix: nothing is sent without a yes, and requests are built right."""

import json
import os
import sys
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(__file__))

import fix  # noqa: E402

ZERO = "00000000-0000-0000-0000-000000000000"
QUOTA_SVC = "/providers/Microsoft.Support/services/" + ZERO


class FakeAz:
    """Answers az rest calls by URL fragment and records writes."""

    def __init__(self, gets):
        self.gets = gets
        self.writes = []

    def rest(self, method, url, body=None):
        if method != "get":
            self.writes.append((method, url, body))
            return {"properties": {"supportTicketId": "1234"}}
        for frag, value in self.gets.items():
            if frag in url:
                return value
        raise fix.FixError(f"unexpected GET {url}")


def quota_gets():
    return {
        "problemClassifications": {"value": [
            {"id": QUOTA_SVC + "/problemClassifications/vm", "properties": {"displayName": "Compute-VM (cores-vCPUs) subscription limit increases"}},
            {"id": QUOTA_SVC + "/problemClassifications/web", "properties": {"displayName": "App Service"}}]},
        "Microsoft.Support/services": {"value": [
            {"id": QUOTA_SVC, "properties": {"displayName": "Service and subscription limits (quotas)"}}]},
        "/me?": {"givenName": "Ada", "surname": "Admin", "mail": "admin@contoso.com", "usageLocation": "US"},
        "Microsoft.Web": {"value": [{"name": {"value": "B3 VMs"}, "limit": 0, "currentValue": 0}]},
    }


class QuotaTests(unittest.TestCase):
    def test_picks_the_app_service_classification(self):
        rows = quota_gets()["problemClassifications"]["value"]
        self.assertTrue(fix.pick_classification(rows)["id"].endswith("/web"))

    def test_contact_maps_country_and_needs_email(self):
        c = fix.contact_from_me({"givenName": "A", "surname": "B", "mail": "a@contoso.com", "usageLocation": "GB"}, None, "UTC")
        self.assertEqual(c["country"], "GBR")
        with self.assertRaises(fix.FixError):
            fix.contact_from_me({"usageLocation": "US"}, None, "UTC")
        with self.assertRaises(fix.FixError):
            fix.contact_from_me({"mail": "a@contoso.com", "usageLocation": "ZZ"}, None, "UTC")

    def test_declining_sends_nothing(self):
        fake = FakeAz(quota_gets())
        with mock.patch.object(fix, "rest", side_effect=fake.rest), mock.patch("builtins.input", return_value="no"):
            self.assertEqual(fix.fix_quota(ZERO, "eastus2", "B3", 2, None, None, "UTC", False), 1)
        self.assertEqual(fake.writes, [])

    def test_yes_opens_one_ticket_with_the_request(self):
        fake = FakeAz(quota_gets())
        with mock.patch.object(fix, "rest", side_effect=fake.rest), mock.patch("builtins.input", return_value="yes"):
            self.assertEqual(fix.fix_quota(ZERO, "eastus2", "B3", 2, None, None, "UTC", False), 0)
        (method, url, body), = fake.writes
        self.assertEqual(method, "put")
        self.assertIn("/providers/Microsoft.Support/supportTickets/nerdio-kit-quota-", url)
        p = body["properties"]
        self.assertTrue(p["problemClassificationId"].endswith("/web"))
        self.assertIn("B3", p["description"])
        self.assertIn("current limit is 0", p["description"])
        self.assertEqual(p["contactDetails"]["country"], "USA")
        self.assertTrue(p["title"].startswith(fix.TICKET_PREFIX))


class VcpuTests(unittest.TestCase):
    def test_sends_quota_api_request_after_yes(self):
        fake = FakeAz({"Microsoft.Quota/quotas": {"properties": {"limit": {"value": 10}}}})
        with mock.patch.object(fix, "rest", side_effect=fake.rest), mock.patch("builtins.input", return_value="yes"):
            self.assertEqual(fix.fix_vcpu(ZERO, "eastus2", "standardDSv5Family", 48, False), 0)
        (method, url, body), = fake.writes
        self.assertIn("Microsoft.Compute/locations/eastus2/providers/Microsoft.Quota/quotas/standardDSv5Family", url)
        self.assertEqual(body["properties"]["limit"]["value"], 48)


class RoleTests(unittest.TestCase):
    def test_activates_the_specific_roles_before_global_admin(self):
        eligible = {"Cloud Application Administrator": "c", "Privileged Role Administrator": "p", "Global Administrator": "g"}
        self.assertEqual(fix.entra_plan(set(), eligible, True),
                         [("Cloud Application Administrator", "c"), ("Privileged Role Administrator", "p")])

    def test_falls_back_to_global_admin(self):
        self.assertEqual(fix.entra_plan(set(), {"Global Administrator": "g"}, True), [("Global Administrator", "g")])

    def test_nothing_when_already_active(self):
        self.assertEqual(fix.entra_plan({"Global Administrator"}, {}, True), [])
        self.assertEqual(fix.entra_plan({"Cloud Application Administrator"}, {"Privileged Role Administrator": "p"}, False), [])

    def test_declining_activates_nothing(self):
        calls = []

        def fake_az(args):
            if args[:2] == ["ad", "signed-in-user"]:
                return ZERO
            return []

        def fake_rest(method, url, body=None):
            calls.append(method)
            if "transitiveMemberOf" in url:
                return {"value": []}
            if "roleEligibilityScheduleInstances" in url and "graph" in url:
                return {"value": [{"roleDefinitionId": "c", "directoryScopeId": "/",
                                   "roleDefinition": {"displayName": "Cloud Application Administrator"}}]}
            return {"value": []}

        with mock.patch.object(fix, "az", side_effect=fake_az), mock.patch.object(fix, "rest", side_effect=fake_rest), \
             mock.patch("builtins.input", return_value=""):
            self.assertEqual(fix.fix_roles(ZERO, False, 4, False), 1)
        self.assertNotIn("post", calls)
        self.assertNotIn("put", calls)


if __name__ == "__main__":
    unittest.main()
