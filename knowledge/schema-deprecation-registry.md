# Google Search Structured-Data Feature Registry

**Status:** Primary-source reconciled baseline  
**Registry version:** 2.0.0  
**Last reconciled:** 2026-07-10  
**Next scheduled review:** 2026-10-10, or immediately after a Google Search structured-data announcement  
**Primary consumers:** schema validation workflows, SEO E-commerce Agent, and content agents  
**Canonical source path:** `knowledge/schema-deprecation-registry.md`

## Purpose

This registry governs **Google Search feature eligibility** and blocks the kit from generating, validating, scoring, or promising retired, restricted, or materially changed displays. It does not determine whether a term remains in schema.org or another product consumes it.

## Evidence and decision rules

Use these labels:

- `VERIFIED_CURRENT`: confirmed against a current Google-owned primary source on the reconciliation date.
- `CONTEXT_DEPENDENT`: the vocabulary or another Google feature may still use the markup, but the named Search display is unavailable or limited.
- `REVERIFY_AT_RUN`: the answer is time-sensitive enough that a client-facing recommendation must check the current Google documentation again.
- `UNVERIFIED`: not confirmed by a primary source. Do not use in executable scoring or client-facing claims.

Apply these rules in order:

1. Confirm the page actually contains the visible information represented by the markup.
2. Confirm the schema.org type and properties are semantically correct.
3. Confirm the desired Google Search feature still appears in the current Search Gallery or current feature documentation.
4. Run the current Rich Results Test when the feature is supported.
5. Explain that valid markup creates eligibility only. It does not guarantee display, ranking, traffic, or inclusion in an AI response.
6. Never replace a retired type with an unrelated type merely to preserve a visual enhancement.

## Canonical feature states

Consumers must emit one of these machine-readable decisions:

- `SUPPORTED`: current Google documentation supports the requested Search feature and the page may be eligible.
- `RETIRED`: the named Google Search display is no longer available.
- `RESTRICTED`: support exists only for a documented class of sites, pages, regions, or use cases.
- `CONTEXT_DEPENDENT`: the markup may serve another Google product or a narrower feature, but not the requested display.
- `UNKNOWN`: current primary documentation was not checked or is ambiguous.

`UNKNOWN` blocks generation of a promised Search enhancement.

## Google Search displays that are retired or no longer broadly available

| Former Search feature | Current Google Search status | Effective history | Registry decision | Semantically safe action |
|---|---|---|---|---|
| `HowTo` rich result | Retired on desktop and mobile | Removed in September 2023 | `VERIFIED_CURRENT` | Do not recommend `HowTo` for a Google Search enhancement. Keep step content in accessible HTML. Retain markup only when another documented consumer requires it and the markup remains accurate. |
| `FAQPage` rich result | No longer shown in Google Search | Restricted to authoritative government and health sites in August 2023; rich result stopped appearing 2026-05-07; report, Rich Results Test, and appearance-filter support removed June 2026; Search Console API support through August 2026 | `VERIFIED_CURRENT` | Do not create or retain `FAQPage` for a Google Search benefit. Use ordinary question-and-answer HTML. Use `QAPage` only for genuine user-submitted questions with answers, not publisher-written FAQs. |
| Course Info rich result | Phased out | Announced 2025-06-12; Search Console and Rich Results Test support removed 2025-09-09 | `VERIFIED_CURRENT` | Do not confuse the retired **Course Info** display with the still-supported **Course list** feature. Use current Course list guidance only when the page and eligibility requirements match. |
| `ClaimReview` rich result | Phased out | Announced 2025-06-12; reporting/test support removed 2025-09-09 | `VERIFIED_CURRENT` | No schema-driven replacement. Use accurate `Article` or `NewsArticle` markup only when the page is actually an article. Preserve editorial fact-check methodology in visible content. |
| Estimated Salary rich result | Phased out | Announced 2025-06-12; reporting/test support removed 2025-09-09 | `VERIFIED_CURRENT` | Do not substitute another type. A specific job page may use current `JobPosting` guidance, including salary data that is visible and accurate. |
| Learning Video rich result | Phased out | Announced 2025-06-12; reporting/test support removed 2025-09-09 | `VERIFIED_CURRENT` | Use current `VideoObject` guidance only when the page contains an eligible video. Do not imply that generic video markup restores the retired learning display. |
| `SpecialAnnouncement` rich result | Phased out | Announced 2025-06-12; reporting/test support removed 2025-09-09 | `VERIFIED_CURRENT` | Use `Event`, `Article`, `WebPage`, or another type only when it truthfully describes the page. There is no direct replacement. |
| Vehicle Listing rich result | Phased out | Announced 2025-06-12; reporting/test support removed 2025-09-09 | `VERIFIED_CURRENT` | A genuinely purchasable vehicle may qualify for current `Product` or merchant-listing markup. Do not promise the former vehicle-listing display. |
| Practice Problem rich result | No longer shown | Documentation removed 2026-01-06 after the feature was retired | `VERIFIED_CURRENT` | Keep educational exercises in useful HTML. Use another type only when the content independently meets that type's current requirements. |

## Special cases that must not be collapsed into â€œdeprecatedâ€

| Markup or feature | Current handling |
|---|---|
| Book Actions | Google announced a phase-out in June 2025, but later removed the deprecation banner because another Google feature still uses the markup. Treat the use case as `CONTEXT_DEPENDENT` and recheck the current Book Actions documentation before implementation. |
| `Course` | Course Info was retired, but the Google Search Gallery still lists Course list. Identify the requested display before advising. |
| `Dataset` | Google documents Dataset markup for Dataset Search. Do not describe it as a general web-search rich result or remove it merely because it is absent from another feature list. |
| schema.org vocabulary after a Search retirement | Vocabulary survival does not mean Google Search support. Conversely, loss of a Search display does not make accurate schema.org markup invalid for every other consumer. |

## Current-feature allowlist policy

Do not maintain a frozen â€œstill live foreverâ€ list. At execution time, compare the requested feature with the current Google Search Gallery. As of this reconciliation, the gallery includes supported documentation for features such as:

- Article, Breadcrumb, Event, Job posting, Local business, Organization, Product, Product variant, Q&A, Recipe, Review snippet, Software app, Video, and other feature-specific types.
- Course list and Dataset, subject to their own narrow eligibility and product context.

Gallery presence alone is insufficient; the implementation must also meet current feature, policy, technical, and visible-content requirements.

## Replacement decision protocol

When a requested display is unavailable:

1. State: **â€œThe former Google Search display is retired or unavailable.â€**
2. State whether the underlying schema.org vocabulary may still be valid elsewhere.
3. Identify the user's real objective: semantic description, Search appearance, product eligibility, accessibility, or data interchange.
4. Recommend a different type only when the page truthfully meets that type's definition.
5. Preserve useful visible content and remove any unsupported promise of a Search enhancement.
6. Record the primary source, check date, and reviewer in the audit output.

## Execution and evidence controls

Load this registry before schema generation, but recheck current Google documentation for any `VERIFY_AT_RUN` or time-sensitive state. Reuse one validation artifact per page and schema graph rather than duplicating property findings across reports. Parse untrusted markup with bounded tools, never execute embedded scripts, and redact personal or confidential values that are not required for validation. A workflow claim such as â€œeligibleâ€ or â€œretiredâ€ must identify the tested page, visible-content evidence, registry state, validation method, date, and any live Search or Merchant Center confirmation available.

## Required registry output

Every schema recommendation must record:

- requested user objective and requested Search feature
- canonical feature state
- current primary-source URL and check date
- semantic type decision
- visible-content parity result
- validation method and result
- limitations and no-guarantee statement

## Failure and escalation conditions

Stop generation and mark the recommendation `BLOCKED` when:

- The requested feature is absent from current Google documentation and no current primary source confirms support.
- The proposed markup describes content that is hidden, fabricated, or materially different from the page.
- Rating, review, price, availability, medical, legal, financial, or regulated claims cannot be substantiated.
- The current documentation conflicts with this registry.

When current Google documentation conflicts with this file, Google is the source of truth. Record the conflict and update this registry before continuing.

## Primary sources

- Google Search structured-data gallery: https://developers.google.com/search/docs/appearance/structured-data/search-gallery
- Google Search documentation updates: https://developers.google.com/search/updates
- June 2025 Search-feature phase-out announcement: https://developers.google.com/search/blog/2025/06/simplifying-search-results
- September 2023 HowTo change: https://developers.google.com/search/blog/2023/09/structured-data-changes
- August 2023 FAQ restriction: https://developers.google.com/search/blog/2023/08/howto-faq-changes
