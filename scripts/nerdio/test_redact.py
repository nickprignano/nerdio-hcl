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


if __name__ == "__main__":
    unittest.main()
