---
status: accepted
date: 2026-10-17
decision-makers: [maintainers]
---

# 0018. License the kit under Apache-2.0

## Context and Problem Statement

The repo and knowledge base will go public for the community, and without a license nobody else
may reuse them. People will copy and adapt the modules into their own repos, at work included,
and vendors may reuse the code too. Which license should the kit's own code use?

## Considered Options

- Apache-2.0
- MIT
- MPL-2.0 (what HashiCorp's providers use)

## Decision Outcome

Chosen option: "Apache-2.0", because it is permissive, is on almost every company's approved
list, and adds an explicit patent grant and patent-retaliation clause that MIT lacks.

- `LICENSE` holds the unmodified Apache-2.0 text; `NOTICE` names the copyright holder and lists
  the third-party components the kit downloads or calls, each under its own terms.
- The license covers only this repository. Nerdio's provider and app (no license, see
  [0013](0013-unlicensed-code-reference-only.md)), WDOT (MIT plus a Microsoft sample-code EULA),
  Terraform and Packer (BSL 1.1) and the providers (MPL-2.0) are not relicensed or bundled.

### Consequences

- Good, because companies can adopt and modify the kit without a legal review stalling on the
  license itself.
- Good, because contributions come in under the same terms (Apache-2.0 section 5), so no CLA is
  needed.
- Bad, because unlike MPL-2.0, changes people make in their own copies don't have to be shared
  back.
- Neutral, because a new third-party component the kit fetches needs a NOTICE line.

## More Information

Not legal advice. Revisit if Nerdio licenses its provider in a way that affects how the kit
uses it.
