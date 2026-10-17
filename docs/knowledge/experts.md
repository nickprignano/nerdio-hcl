---
title: "Experts we follow"
summary: "How we choose which Nerdio and AVD experts the KB follows: the study method, the scores, and the published list"
topic: curation
status: verified
last_reviewed: 2026-10-17
---

# Experts we follow

The weekly digest ([curation.md](curation.md#weekly-digest-kb-curator)) watches a set of people
who write about Nerdio Manager and Azure Virtual Desktop. This page explains how that list is
chosen, so anyone can check it, re-run it or challenge it. The data is in
[experts.yaml](experts.yaml), and the tables below are generated from it.

<!-- BEGIN GENERATED: experts-balance (from experts.yaml; run scripts/kb/build.py) -->
Last scored 2026-10-17: 15 tracked (5 nerdio, 4 unknown, 3 partner, 2 independent, 1 microsoft), 7 on the watch list, 4 declined, 0 nominated and waiting to be scored.
<!-- END GENERATED: experts-balance -->

## The method

It works like a small systematic review: the rules are fixed before anyone is scored, they're
applied the same way to everyone, and every score points at evidence.

### 1. Find candidates in several places

One list (a "top voices" post, say) brings its author's blind spots with it, so candidates come
from several channels, and each entry records which ones found it (`found_via`):

- The Microsoft MVP directory, in the Azure Virtual Desktop and Windows categories
- Speakers at NerdioCon, Nerdio webinars and Nerdio's YouTube channel
- GitHub: users and repos that mention Nerdio, and the KB's prior-art searches
- Blogs that post about Nerdio or AVD more than once
- Snowballing: who the people already on the list link to, cite or present with
- Nominations through the **Suggest an expert to follow** issue form

### 2. Apply the gates

A candidate must pass all four gates to be tracked. Organisations (Nerdio's YouTube channel, Microsoft's AVD blog) go through the same gates and scores as people. Failing identity or originality declines
them; failing only recency or feed puts them on the watch list if their score is high enough.

| Gate | Passes when |
|---|---|
| Original | They publish their own technical content, not just reshares or marketing |
| Recent | They've posted about Nerdio or AVD in the last 12 months |
| Feed | A free, machine-readable feed exists: blog RSS or Atom, a YouTube channel or a GitHub account (X isn't one; see [curation.md](curation.md#tracking-x-accounts-option-not-enabled)) |
| Identity | We know who's behind every account we'd watch: one of their own profiles links the others, or we watch only one account |

### 3. Score five things from 0 to 3

| Score | 0 | 1 | 2 | 3 |
|---|---|---|---|---|
| Relevance | Rarely Nerdio or AVD | Occasionally | A regular topic | Their main topic |
| Depth | Announcements only | Overviews | How-tos with steps | Code, scripts or gotchas others can reuse |
| Recency | Nothing on topic in 12 months | Within 12 months | Within 6 months | Within 3 months |
| Track record | Unknown | Some engagement | Cited or reused by others | Widely cited, MVP or maintainer of a tool people use |
| Feedability | No free feed | A feed, mostly off topic | A feed that keyword filters can fix | A clean, on-topic feed |

The total is out of 15.

- **Tracked:** all gates pass and the total is 10 or more. They get a `[[source]]` in
  [sources.toml](sources.toml) with `expert = "<id>"`.
- **Watch:** identity and originality pass and the total is 6 or more. Re-checked each review, not
  in the digest.
- **Declined:** everything else, with the reason, so the same person isn't re-researched for
  nothing.

`scripts/kb/validate.py` enforces these rules: an entry's status must match its gates and scores,
every tracked expert must have a source, and every source with an `expert` must be tracked.

**Affiliation is recorded but not scored.** Nerdio and Microsoft staff often know the product
best, so they aren't marked down. The summary above shows the mix, so a list that's all one
company's voices is visible.

### 4. Measure and review

- **Yield:** the monthly freshness check reads recent digest issues and counts, per tracked
  expert, how many of their items were ticked as worth adding. A source that lists nothing, or
  only items nobody ticks, is flagged to re-score or narrow with `keywords`.
- **Cadence:** everyone is re-scored once per 90-day build window
  ([decision 0010](decisions/0010-roadmap-horizon.md)). The freshness check lists anyone not
  re-scored in 90 days and any nomination waiting to be scored. Anyone silent on the topic for
  six months fails the recency gate and moves to the watch list.
- **Nominations:** the issue form adds the person as `nominated`. When a maintainer labels it
  `kb-accepted`, the feedback workflow opens a PR, and the maintainer scores them in that PR.

### What's recorded about people

Only what they publish professionally: the name they use, their public links, and their
affiliation if they state it. No emails, locations or other personal details. Anyone listed can
ask to be removed by opening an issue.

## Tracked

<!-- BEGIN GENERATED: experts-tracked (from experts.yaml; run scripts/kb/build.py) -->
| Name | Affiliation | Links | Score (rel/depth/recency/record/feed) | Latest Nerdio or AVD post | Notes |
|---|---|---|---|---|---|
| Aaron Parker | nerdio | [blog](https://stealthpuppy.com/), [GitHub](https://github.com/aaronparker) | 14 (3/3/2/3/3) | [2026-06-09](https://stealthpuppy.com/) | Maintains Evergreen and the aaronparker/nerdio scripts. Latest: "Evergreen Workbench is Generally Available". |
| Dominiek Verham | partner | [blog](https://dominiekverham.com/) | 14 (3/2/3/3/3) | [2026-10-09](https://dominiekverham.com/) | Microsoft MVP and Nerdio NVP. The most Nerdio-focused independent blog found. Latest: "Configuring Nerdio Manager for MSP: post-installation checklist". |
| Marcel Meurer | independent | [blog](https://blog.itprocloud.de/), [GitHub](https://github.com/MarcelMeurer) | 14 (2/3/3/3/3) | [2026-09-02](https://blog.itprocloud.de/) | Deep AVD gotchas. Makes Hydra, an AVD management tool that competes with Nerdio, so filter out product posts. Latest: "Azure Virtual Desktop Hybrid With Hydra Is General Available". |
| Wayne Bellows | nerdio | [blog](https://modern-euc.com/), [GitHub](https://github.com/WayneBellows) | 14 (3/3/3/2/3) | [2026-10-08](https://modern-euc.com/) | Nerdio TAM. Weekly AVD image and FSLogix posts, plus scripted actions on GitHub. Latest: "How to Update an AVD Golden Image to Windows 11 26H2 Without a Bad Monday". |
| Microsoft Azure Virtual Desktop blog | microsoft | [blog](https://techcommunity.microsoft.com/category/azure/blog/azurevirtualdesktopblog), [GitHub](https://github.com/avdaccelerator) | 13 (3/1/3/3/3) | [2026-10-01](https://techcommunity.microsoft.com/) | Official AVD announcements. Latest: "Now generally available: Regional resiliency for Azure Virtual Desktop". |
| Nerdio (YouTube channel) | nerdio | [blog](https://getnerdio.com/blog/), [YouTube](https://www.youtube.com/channel/UClzdOrR9o0I05hnnByEKIKA), [GitHub](https://github.com/Get-Nerdio) | 13 (3/2/3/3/2) | none found | Webinars and release walkthroughs. Nerdio's blog has no feed. |
| Cristian Schmitt Nieto | partner | [blog](https://schmitt-nieto.com/), [GitHub](https://github.com/schmittnieto) | 12 (2/3/3/2/2) | [2026-09-22](https://schmitt-nieto.com/) | Nerdio NVP. MIT-licensed Nerdio scripted actions; maintains the awesome-azure-virtual-desktop list. Latest: "Azure Local: Entra Joined AVD Session Hosts with PowerShell". |
| Duo Infernale (Michele Blum and Flavio Meyer) | unknown | [blog](https://duo-infernale.ch/) | 12 (3/2/3/1/3) | [2026-10-14](https://duo-infernale.ch/) | Frequent AVD how-tos. Only the blog is watched. Identity: accounts aren't cross-linked, so only one is watched. Latest: "Azure Virtual Desktop: Now Available in Your Region". |
| Neil McLoughlin | nerdio | [blog](https://virtualmanc.co.uk/), [YouTube](https://www.youtube.com/channel/UCS5W4f_rZexpCnBF1tSh1XA), [GitHub](https://github.com/virtualmanc) | 12 (3/2/2/3/2) | [2026-07-15](https://virtualmanc.co.uk/) | Nerdio TAM and Microsoft MVP. His new blog, virtualdesktops.community, couldn't be checked yet. Latest: "Context-Based Redirection in AVD & Windows 365 (guide)". |
| markovich.io | independent | [blog](https://markovich.io/), [GitHub](https://github.com/wmarkovich) | 12 (3/2/3/1/3) | [2026-10-13](https://markovich.io/) | Posts almost daily without saying how; spot-check a sample for accuracy at the next review. Latest: "Windows 11 Image Versioning for AVD: Testing Copilot Search and AI Features Before They Hit Production". |
| Johan Vanneuville | partner | [blog](https://johanvanneuville.com/) | 11 (3/2/1/2/3) | [2026-03-16](https://johanvanneuville.com/) | Nerdio NVP. Nerdio scripted actions and install guides; quiet since March 2026. Latest: "Pilot Nerdio to a succesfull install". |
| ModernWorkspaceHub | unknown | [blog](https://modernworkspacehub.com/), [GitHub](https://github.com/durrante) | 11 (2/3/3/1/2) | [2026-09-09](https://modernworkspacehub.com/) | Maintains an AVD monitoring baseline (a fork of Microsoft's AMBA alerts). Latest: "Azure VM OS disk and C: drive sizes don". |
| Alex ter Neuzen | unknown | [blog](https://www.gettothe.cloud/), [GitHub](https://github.com/GetToThe-Cloud) | 10 (1/3/3/1/2) | [2026-09-24](https://www.gettothe.cloud/) | AVD monitoring workbooks and KQL. Only the blog is watched, filtered to AVD. Latest: "Azure Virtual Desktop \| Sessionhost monitoring 2.0". |
| Christiaan Brinkhoff | nerdio | [blog](https://christiaanbrinkhoff.com/), [YouTube](https://www.youtube.com/channel/UCP894c8_Rgop-qANoVK6Vkg) | 10 (2/1/2/3/2) | [2026-02-26](https://christiaanbrinkhoff.com/) | Joined Nerdio in 2026 from Microsoft's Windows 365 and AVD team. Mostly overviews. Latest: "Azure Virtual Desktop for hybrid environments". |
| Travis Roberts (Ciraltos) | unknown | [blog](https://www.ciraltos.com/), [YouTube](https://www.youtube.com/channel/UCuB24cID6NnypDWSLe4gfqA) | 10 (1/2/3/2/2) | [2026-09-09](https://www.ciraltos.com/) | AVD explainers. Only the blog is watched, filtered to AVD. Identity: accounts aren't cross-linked, so only one is watched. Latest: "Azure Virtual Desktop Hybrid Is Now GA: 6 Reasons to Use It, and 2 Reasons to Reconsider". |
<!-- END GENERATED: experts-tracked -->

## Watch list

<!-- BEGIN GENERATED: experts-watch (from experts.yaml; run scripts/kb/build.py) -->
| Name | Affiliation | Links | Score (rel/depth/recency/record/feed) | Latest Nerdio or AVD post | Notes |
|---|---|---|---|---|---|
| Dean Cefola (Azure Academy) | independent | [YouTube](https://www.youtube.com/channel/UC-MXgaFhsYU8PkqgKBdnusQ), [GitHub](https://github.com/DeanCefola) | 11 (3/3/0/3/2) | [2025-10-07](https://www.youtube.com/watch?v=bAB_gO8GU0o) | Fails: recent. Long-running AVD video series. No dated AVD video in the last 12 months was found; YouTube Shorts weren't checked. |
| Aresh Sarkari | unknown | [blog](https://askaresh.com/) | 9 (1/3/1/2/2) | [2026-10-08](https://askaresh.com/) | Mostly Windows 365 now. Identity: accounts aren't cross-linked, so only one is watched. Latest: "Windows 365 Local Admin - Cloud PC Configurations vs User Settings + PowerShell (Graph REST API)". |
| Mobile Jon | partner | [blog](https://mobile-jon.com/), [YouTube](https://www.youtube.com/channel/UCJBM-j8va7lrwTZBWSXt7vw), [GitHub](https://github.com/mobilejon) | 9 (1/3/1/2/2) | [2026-01-10](https://mobile-jon.com/2026/01/10/building-azure-virtual-desktop-images-powered-by-nerdio/) | Nerdio NVP. Deep when on topic, but mostly writes about Intune. |
| Shabaz Darr | partner | [YouTube](https://www.youtube.com/channel/UCt5sNdu14RterwDfEDEJidQ) | 8 (2/2/0/3/1) | [2025-07-22](https://www.youtube.com/watch?v=k27nZcv7sew) | Fails: recent. Microsoft MVP and Nerdio NVP. Newest Nerdio video found is from July 2025; the channel moved to a new ID. |
| Bas van Kaam | nerdio | [blog](https://www.basvankaam.com/) | 7 (2/2/0/3/0) | [2023-04-11](https://www.basvankaam.com/) | Fails: recent. No posts since 2023. Latest: "The Azure Virtual Desktop Security Guidelines Cheat Sheet - v1.0". |
| Marius Sandbu | unknown | [blog](https://msandbu.org/) | 7 (0/3/0/3/1) | none found | Fails: recent. Active, but not on Nerdio or AVD now. Identity: accounts aren't cross-linked, so only one is watched. |
| Sander Rozemuller | unknown | [blog](https://rozemuller.com/), [GitHub](https://github.com/srozemuller) | 7 (0/3/0/3/1) | none found | Fails: recent. Strong AVD automation history; recent posts are all Intune. Identity: accounts aren't cross-linked, so only one is watched. |
<!-- END GENERATED: experts-watch -->

## Declined

<!-- BEGIN GENERATED: experts-declined (from experts.yaml; run scripts/kb/build.py) -->
| Name | Affiliation | Links | Score (rel/depth/recency/record/feed) | Latest Nerdio or AVD post | Notes |
|---|---|---|---|---|---|
| AVD Community Newsletter | independent | [blog](https://avdcommunity.com/category/newsletter/) | 11 (3/0/3/2/3) | [2026-10-02](https://avdcommunity.com/category/newsletter/) | Fails: original. A curated roundup, not original content. Used to find new people at each review. |
| Patrick Coble | unknown | [blog](https://vdihacker.com/) | 6 (1/2/0/3/0) | none found | Fails: recent, feed, identity. Nerdio NVP. His site couldn't be read and no feed was confirmed. |
| Dane Young | partner | [blog](https://blog.youngtech.com/) | 5 (0/2/0/2/1) | none found | Fails: recent. Nerdio NVP. Nothing on Nerdio or AVD in the current feed. Identity: accounts aren't cross-linked, so only one is watched. |
| Fabian Rodrigues | unknown |  | 0 (0/0/0/0/0) | none found | Fails: original, recent, feed, identity. Couldn't identify a Nerdio or AVD author by this name. |
<!-- END GENERATED: experts-declined -->

## Nominated, not scored yet

<!-- BEGIN GENERATED: experts-nominated (from experts.yaml; run scripts/kb/build.py) -->
None waiting.
<!-- END GENERATED: experts-nominated -->
