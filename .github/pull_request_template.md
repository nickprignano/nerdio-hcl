## What changes

Before:

After:

## Guardrails ([docs/guardrails.md](../docs/guardrails.md))

- [ ] No real IDs, domains, IPs, emails, secrets or employer names (CI also scans)
- [ ] Done in HCL where Terraform or Packer can do it; any script is thin glue
- [ ] Works from Cloud Shell in a browser
- [ ] No copied code from unlicensed repos; facts cite their source in the KB
- [ ] Security not weakened for automation (or a decision record says why)
- [ ] Knowledge base updated with anything learned
