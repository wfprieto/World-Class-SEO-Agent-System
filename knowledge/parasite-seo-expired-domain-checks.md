# Site Reputation and Expired-Domain Abuse Controls

**Status:** Primary-source reconciled baseline  
**Version:** 2.0.0  
**Last reconciled:** 2026-07-10  
**Next scheduled review:** 2026-10-10, or immediately after a Google spam-policy change  
**Primary consumers:** Negative SEO & Security Agent, Senior SEO Strategist Agent, and programmatic SEO governance  
**Canonical source path:** `knowledge/parasite-seo-expired-domain-checks.md`

## Purpose

This file supports defensive audits, acquisition due diligence, and policy-risk analysis. It does not justify alleging intent or treating topical expansion, freelance or affiliate content, user-generated content, or an expired-domain purchase as automatically abusive.

## Evidence labels

- `OBSERVED`: directly verified content, ownership, archive, backlink, Search Console, or technical evidence.
- `POLICY_MATCH`: observed facts closely match a current Google policy example or definition.
- `ANALYSIS`: reasoned risk assessment; intent or primary purpose is inferred.
- `UNKNOWN`: required evidence is unavailable.
- `CONFIRMED_ACTION`: a Search Console manual action or other direct enforcement notice is available.

Use “policy-risk pattern” unless enforcement is directly confirmed.

## Current policy anchors

Google introduced explicit spam policies for expired domain abuse, scaled content abuse, and site reputation abuse in March 2024. The current policy language is the source of truth.

### Site reputation abuse

Current definition: third-party content is published on a host mainly because of the host's established ranking signals, with the goal of ranking better than the content could on its own.

Important boundaries:

- Third-party content alone is not a violation.
- Freelance, syndicated, user-generated, native advertising, affiliate, and merchant-sourced coupon content are not automatically violations.
- First-party involvement or editorial oversight does not cure an arrangement whose main purpose is to exploit the host's ranking signals.
- Google may evaluate a starkly different site section independently even when it is not a spam-policy violation.

### Expired domain abuse

Current definition: an expired domain is purchased and repurposed primarily to manipulate rankings by hosting content that provides little to no user value.

A changed topic or new owner is evidence to investigate, not proof. Evaluate primary purpose, user value, historical identity, link inheritance, claims, and the actual content strategy.

### Adjacent scaled content abuse

Scaled content abuse concerns many pages created primarily to manipulate rankings and providing little or no value, regardless of whether AI, scraping, translation, manual production, or another method created them. Route large-scale page systems to the programmatic SEO governance skill.

## Enforcement distinction

Keep these states separate:

- `POLICY_RISK`: observed facts resemble a current spam-policy definition or example.
- `MANUAL_ACTION_CONFIRMED`: Search Console identifies a manual action.
- `AUTOMATED_IMPACT_POSSIBLE`: Google states automated systems or demotions may apply, but the audited traffic change is not proven to result from them.
- `SECTION_EVALUATED_INDEPENDENTLY`: a site section may stop benefiting from broader site signals without a spam violation or penalty.

Do not call an inferred competitor pattern a penalty, manual action, or confirmed violation. Public-facing competitor claims require legal/compliance review and should describe observable facts, not motives.

## Site reputation abuse evidence matrix

| Check | Observable evidence | Risk interpretation |
|---|---|---|
| Content origin | Separate company, white-label operator, freelancer network, user, or licensed feed | Third-party status alone is neutral; document it |
| Topic and audience fit | Section materially diverges from the host's established purpose and reader expectations | Supports risk analysis, not intent by itself |
| Distribution pattern | Same or near-identical page appears across multiple authority hosts | Stronger evidence of an external ranking-distribution model |
| Commercial arrangement | Revenue share, placement fee, lead sale, affiliate model, or outsourced operation | Relevant context; not automatically abusive |
| Search dependency | Section appears designed primarily for organic acquisition with little direct promotion or user integration | Supports inferred purpose when combined with other evidence |
| Editorial/user value | Original reporting, genuine editorial work, useful service, first-party integration, and direct audience demand | Can reduce risk but does not override evidence of ranking exploitation |
| Enforcement | Search Console manual action and affected examples | `CONFIRMED_ACTION` |

## Expired-domain acquisition checks

1. Verify domain and ownership history through multiple lawful sources.
2. Review archived pages across representative dates and paths.
3. Compare historical topics, audiences, organizations, trademarks, and claims with the proposed use.
4. Inspect backlink destinations, anchor context, referring-site relevance, redirects, and link persistence.
5. Ask the seller for Search Console manual-action and security-issue evidence when possible.
6. Check index status, malware, hacked content, legal disputes, brand confusion, email reputation, and prior abuse.
7. Document the proposed user value independent of inherited rankings.
8. Model a clean-domain alternative. If the business case fails without inherited authority, escalate the manipulation risk.

## Risk classification

- `LOW`: legitimate continuity or a valuable new use, transparent ownership, no material inherited-link mismatch, and no policy-match evidence.
- `MODERATE`: meaningful topic/ownership shift or third-party section with incomplete evidence; requires owner review and monitoring.
- `HIGH`: multiple observed signals closely match policy examples or the strategy materially depends on inherited/host ranking signals.
- `CONFIRMED`: a current manual action or direct enforcement notice identifies the issue.

Never state that a competitor “is violating” the policy based only on public inference. State the observed pattern, policy similarity, missing evidence, and confidence.

## Response and remediation

### For a host with a risky third-party section

- Stop expansion while evidence is reviewed.
- Identify who creates, controls, monetizes, and promotes the section.
- Remove, relocate, or substantively redesign pages whose primary purpose is ranking exploitation.
- `noindex` can remove pages from Search when correctly processed, but it is not a substitute for correcting the business and content practice or for responding to a manual action.
- If a manual action exists, follow the notice, correct all affected patterns, document remediation, and submit a reconsideration request when eligible.

### For an expired domain

- Do not preserve unrelated pages or redirects merely to harvest inherited authority.
- Build content for a legitimate user purpose and avoid misleading continuity with the former organization.
- Remove unsupported claims, unsafe redirects, hacked content, and irrelevant inherited pages.
- Monitor links, indexation, manual actions, security issues, and user confusion after launch.

## Privacy, failure, and challenge controls

Store one canonical evidence record for each archive capture, ownership event, backlink observation, or host-section review. Do not publish registrant personal data, private acquisition records, credentials, or confidential commercial arrangements without authorization. If archive history, ownership continuity, editorial control, or current policy cannot be verified, return `UNKNOWN` or `PARTIAL`; do not infer intent. High-impact remediation, acquisition, migration, or manual-action conclusions require an independent challenge and accountable-owner review.

## Required output

Return:

- Scope and current primary policy checked
- Observed facts separated from inferred intent
- Evidence matrix and missing evidence
- Risk classification with confidence
- User, legal, brand, and Search risks
- Required owner/compliance/security handoffs
- Remediation plan, acceptance criteria, and verification method

## Primary sources

- Current Google Search spam policies: https://developers.google.com/search/docs/essentials/spam-policies
- March 2024 policy announcement: https://developers.google.com/search/blog/2024/03/core-update-spam-policies
- November 2024 site-reputation clarification and January 2025 update: https://developers.google.com/search/blog/2024/11/site-reputation-abuse
- Search Console manual actions: https://support.google.com/webmasters/answer/9044175
