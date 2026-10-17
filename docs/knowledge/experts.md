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
Last scored 2026-10-17: 0 tracked (none), 0 on the watch list, 0 declined, 2 nominated and waiting to be scored.
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

A candidate must pass all four gates to be tracked. Failing identity or originality declines
them; failing only recency or feed puts them on the watch list if their score is high enough.

| Gate | Passes when |
|---|---|
| Original | They publish their own technical content, not just reshares or marketing |
| Recent | They've posted about Nerdio or AVD in the last 12 months |
| Feed | A free, machine-readable feed exists: blog RSS or Atom, a YouTube channel or a GitHub account (X isn't one; see [curation.md](curation.md#tracking-x-accounts-option-not-enabled)) |
| Identity | One of their own profiles links to the others, so we know the accounts are the same person |

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
None.
<!-- END GENERATED: experts-tracked -->

## Watch list

<!-- BEGIN GENERATED: experts-watch (from experts.yaml; run scripts/kb/build.py) -->
None.
<!-- END GENERATED: experts-watch -->

## Declined

<!-- BEGIN GENERATED: experts-declined (from experts.yaml; run scripts/kb/build.py) -->
None.
<!-- END GENERATED: experts-declined -->

## Nominated, not scored yet

<!-- BEGIN GENERATED: experts-nominated (from experts.yaml; run scripts/kb/build.py) -->
| Name | Links | Nomination | Notes |
|---|---|---|---|
| Aaron Parker | [blog](https://stealthpuppy.com), [GitHub](https://github.com/aaronparker) |  |  |
| Wayne Bellows | [blog](https://modern-euc.com) |  |  |
<!-- END GENERATED: experts-nominated -->
