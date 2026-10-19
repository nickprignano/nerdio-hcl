import unittest

import redact


class RedactTests(unittest.TestCase):
    def test_masks_ids_ips_emails_domains_and_account_names(self):
        text = ('\x1b[1m~ id = "/subscriptions/11111111-2222-3333-4444-555555555555/rg"\x1b[0m\n'
                'ip_address = "20.30.40.50" address_space 10.50.0.0/20 dns 168.63.129.16\n'
                'owner admin@contoso.onmicrosoft.com in contoso.onmicrosoft.com, subscription "sub-example-lab"\n')
        out = redact.redact(text, ["sub-example-lab"])
        for leaked in ("11111111", "20.30.40.50", "admin@", "contoso", "sub-example-lab", "\x1b"):
            self.assertNotIn(leaked, out)
        for kept in ("10.50.0.0/20", "168.63.129.16", "<id>", "<public-ip>", "<email>", "<account>"):
            self.assertIn(kept, out)

    def test_account_names_mask_whole_words_only(self):
        out = redact.redact("lab admin grants admin consent in sub-lab", ["admin", "sub-lab"])
        self.assertEqual(out, "lab <account> grants <account> consent in <account>")

    def test_resource_ids_lose_their_group_and_resource_names(self):
        rid = ("/subscriptions/x/resourceGroups/rg-acme-net/providers/Microsoft.Network/virtualNetworks/vnet-acme"
               "/subnets/snet-hosts and /providers/Microsoft.Web/locations/eastus2/usages")
        out = redact.redact(rid)
        for leaked in ("acme", "snet-hosts"):
            self.assertNotIn(leaked, out)
        self.assertIn("/providers/Microsoft.Network/virtualNetworks/<name>/subnets/<name>", out)
        self.assertIn("locations/eastus2", out)


if __name__ == "__main__":
    unittest.main()
