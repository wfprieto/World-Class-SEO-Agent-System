# E-commerce SEO Skills

**Status:** Controlled integration baseline  
**Version:** 2.0.0  
**Index category:** `E-commerce Skills`  
**Primary owner:** SEO E-commerce Agent  
**Canonical source path:** `skills/ecommerce-seo-skills.md`

## Shared execution rules

All seven skills use the same controls:

- Evidence states: `OBSERVED`, `PROVIDER_REPORTED`, `USER_SUPPLIED`, `INFERRED`, and `UNKNOWN`. Never present inference or missing data as observation.
- Execution states: `COMPLETE`, `PARTIAL`, `SKIPPED`, `BLOCKED`, and `FAILED`. Completion cannot exceed the evidence and capability tier actually used.
- Metered calls require an explicit estimate, approval, and hard ceiling before execution.
- Do not retain credentials, checkout data, personal information, or raw provider payloads beyond the approved purpose.
- Every recommendation must include evidence, confidence, impact, effort, risk, owner, acceptance criteria, and verification method.
- Current Google Search, Merchant Center, and UCP primary documentation overrides this file when behavior changes.

---

## Skill: `product-page-seo-audit`

### Purpose

Evaluate a product, variant, category, or collection page for buyer usefulness, Search discoverability, merchant-data consistency, media quality, internal discovery, and technical eligibility without substituting heuristics for official requirements.

### Required inputs

- exact URL and expected page type;
- target country, language, currency, device, and buyer intent;
- approved rendered/source evidence;
- target product and variant identity when applicable;
- existing schema result or permission to call `product-schema-validate-generate`;
- Merchant/feed evidence when available.

### Procedure

1. Confirm page type and exact product/variant. Route editorial reviews, internal search, non-commerce pages, and unsupported pages to the appropriate workflow.
2. Record visible product identity, value proposition, price, currency, availability, variant state, seller, primary action, shipping/return disclosure, reviews, identifiers, and media only when observed.
3. Evaluate title link inputs, headings, copy, specifications, decision-support content, trust/policy access, and variant clarity. Treat length and word-count conventions as heuristics, not compliance gates.
4. Evaluate media using separate states for Search structured-data images, Merchant Center main/additional images, on-page user experience, and Core Web Vitals. Do not collapse them into one image check.
5. Check product and variant URLs, preselection, canonicals, breadcrumbs, category links, related products, pagination paths, and crawlable links.
6. Reuse the schema skill result. Do not duplicate its property-level findings. When Merchant data exists, check whether AI-generated feed titles/descriptions use the currently required structured attributes and whether generative-image provenance survives the final delivered asset, using `knowledge/ai-image-labeling.md`.
7. If merchant evidence exists, call or link `merchant-data-consistency-audit`.
8. Hand performance and rendering root causes to the Technical SEO Agent; link rather than duplicate.

### Diagnostic model

Evaluate these dimensions when evidence exists:

- product and variant clarity: 20
- buyer decision support and trust: 20
- merchant-data consistency: 20
- structured-data eligibility: 15
- media quality and policy: 10
- internal discovery and URL behavior: 10
- technical/performance evidence: 5

Report coverage. If merchant data is unavailable, mark that dimension `null` and renormalize evaluated dimensions without implying Merchant Center approval.

### Hard blockers

- tested product or variant cannot be identified;
- page cannot be purchased in the stated market but is being assessed as a merchant listing;
- material price, currency, availability, or variant mismatch;
- page is inaccessible to the approved renderer/fetcher and no valid evidence exists;
- regulated-product review is required and unavailable.

### Output

- page classification and identity map;
- execution state, active tier, score, and coverage;
- observed page facts;
- linked schema and consistency results;
- prioritized recommendations with acceptance criteria;
- blockers, unknowns, and verification plan.

---

## Skill: `product-schema-validate-generate`

### Purpose

Select, validate, and when authorized generate current Product, Offer, AggregateOffer, or ProductGroup JSON-LD that truthfully represents visible page content and the intended Google Search use case.

### Required inputs

- page URL, page type, and purchase capability;
- visible product and offer data;
- existing JSON-LD and initial/rendered HTML evidence;
- exact variant model and identifiers;
- requested objective: product snippet, merchant listing, variant understanding, or semantic data;
- current structured-data registry.

### Procedure

1. Load `knowledge/schema-deprecation-registry.md` and current Google Product documentation.
2. Select the use case:
   - `PRODUCT_SNIPPET` for product information or editorial review pages where direct purchase is not the merchant-listing use case;
   - `MERCHANT_LISTING` for pages where customers can purchase the product from the merchant;
   - `PRODUCT_VARIANTS` when variants need explicit grouping.
3. Validate semantic type, required properties, recommended properties, visible-content parity, identifiers, URLs, and initial-HTML availability.
4. For merchant listings, validate at minimum `Product.name`, `Product.image`, nested `Offer`, active price greater than zero, and corresponding currency. Merchant listings require an `Offer`; product snippets may support `Offer` or `AggregateOffer` under their current rules. Treat availability, URL, condition, shipping, returns, identifiers, seller, and brand according to the current use-case documentation, not a frozen invented checklist.
5. For variants, require a unique variant identifier and product-group identifier, exact variant URLs/preselection, self-contained markup per page, and the appropriate single-page or multi-page model. Use `ProductGroup`, `variesBy`, `hasVariant`, `isVariantOf`, `productGroupID`, or `inProductGroupWithID` only as the selected model requires.
6. Validate reviews and ratings only when genuine, visible, attributable, and compliant with current review-snippet rules.
7. Validate page/feed/schema parity for price, currency, availability, condition, product identity, and variant.
8. Generate corrected JSON-LD only from substantiated inputs. Use placeholders only in a clearly labeled template that cannot be mistaken for deployable markup.
9. Require Rich Results Test and URL Inspection evidence for deployment acceptance when available.

### Scoring

Score by requirement classes, not by accumulating optional features:

- semantic/use-case correctness: 25
- required-property validity: 30
- visible-content and source parity: 20
- variant/identifier integrity: 10
- recommended enrichment: 10
- validation and deployment proof: 5

A required-property failure or visible-content mismatch blocks a pass regardless of numeric score.

### Output

- selected use case and registry state;
- property-level result with `REQUIRED`, `RECOMMENDED`, or `NOT_APPLICABLE` status;
- deployable JSON-LD or non-deployable template state;
- score, coverage, blockers, validation results, and no-guarantee statement.

---

## Skill: `merchant-data-consistency-audit`

### Purpose

Reconcile the exact product and variant across landing page, structured data, merchant feed/account, and safely observable checkout state to identify mismatches that can harm approval, eligibility, or user trust.

### Required inputs

- exact product ID, variant ID, URL, market, language, and currency;
- rendered landing-page evidence;
- structured-data evidence;
- user-approved Merchant Center/API data or dated export;
- checkout evidence only when it can be obtained without a purchase, personal data, or unapproved interaction.

### Procedure

1. Match the same product and variant using stable identifiers and distinguishing attributes.
2. Capture base price, sale price and effective window, eligible member price and membership conditions, currency, availability, condition, title, image, variant attributes, minimum quantity, bundle/multipack state, landing URL, shipping, and returns from each available source with timestamps. When checkout evidence is approved, confirm the same variant remains selectable and purchasable without completing an order.
3. Classify each comparison as `MATCH`, `MISMATCH`, `STALE`, `MISSING`, `MARKET_DIFFERENCE`, or `UNKNOWN`.
4. Separate expected market differences from same-market inconsistencies.
5. Identify update-pipeline causes without guessing: feed cadence, API lag, client-rendered values, variant URL/preselection, sale windows, regional pricing, or stale schema.
6. Prioritize exact reconciliation actions and owner. Do not silently choose one source when business ownership is unresolved.

### Output

- item/variant identity record;
- field-by-source consistency matrix;
- material blocker summary;
- freshness and update-path findings;
- recommendations and re-test plan.

### Failure and fallback

If merchant data is unavailable, return `PARTIAL` with a page/schema baseline and a precise list of account fields needed. Do not call the product Merchant Center-compliant.

---

## Skill: `marketplace-intelligence`

### Purpose

Analyze product-result and seller evidence from approved live sources for a defined query and market, with transparent source coverage and no fabricated competitive data.

### Required inputs

- product, category, or keyword set;
- target country, language, currency, device, and marketplace;
- connected source and source coverage;
- explicit approval and bounded budget for metered calls;
- product-matching rules.

### Procedure

1. Confirm source authorization, terms-compliant access, query plan, expected call count, estimated cost, and approval.
2. Define exact matching and deduplication rules before collection.
3. Collect results with source, timestamp, locale, device, currency, rank/position semantics, and missing fields.
4. Normalize currency only with a cited exchange-rate timestamp; retain original values.
5. Separate identical products, variants, bundles, used/refurbished items, subscriptions, sponsored placements, and unmatched results.
6. Compute descriptive statistics only when sample size and field coverage support them. Use robust methods such as median and IQR; label any outlier rule. Do not default to a standard-deviation rule for skewed prices. Keep sponsored, organic product-result, and marketplace-ranking semantics separate, and do not treat result count as seller share unless the source defines it that way.
7. Report seller, price, shipping, review, media, and listing-pattern observations only within source coverage.
8. Log actual calls and cost.

### Output

- collection specification, coverage, and matched-result inventory;
- pricing and seller analysis with sample sizes and missingness;
- source limitations, recommendations, and cost report.

### Failure and fallback

No approved live source means `BLOCKED` or `SKIPPED`, not estimated marketplace intelligence. Route to page/schema work and list the missing capability.

---

## Skill: `marketplace-keyword-gap`

### Purpose

Identify query-level differences between organic visibility, Google product visibility, and optional marketplace presence using aligned, connected datasets.

### Required inputs

- verified domain and product scope;
- organic ranking dataset;
- Shopping/product-result dataset;
- optional marketplace dataset;
- aligned country, language, device, date window, and query definitions;
- source-specific volume/CPC semantics when requested.

### Procedure

1. Validate dataset ownership, freshness, coverage, and comparable market context.
2. Normalize queries without collapsing distinct intent or variant meaning.
3. Map each query to product/category intent and the relevant landing page.
4. Classify supported states such as `ORGANIC_ONLY`, `PRODUCT_ONLY`, `BOTH`, `NEITHER_IN_OBSERVED_SET`, `MISMATCHED_LANDING_PAGE`, and `INSUFFICIENT_DATA`.
5. Do not interpret absence from a sampled dataset as universal absence.
6. Recommend content, feed, schema, product-data, or prioritization actions based on evidence. Paid bidding recommendations belong to the paid-media owner.
7. Show source, position semantics, volume/CPC provenance, timestamp, and confidence.

### Output

- aligned-query coverage report;
- opportunity tables by state;
- landing-page and product mapping;
- prioritized actions with evidence and limitations.

### Failure and fallback

If one channel is unavailable, return a one-channel baseline and mark cross-channel classification unavailable. Never populate missing volume or CPC.

---

## Skill: `faceted-navigation-governance`

### Purpose

Control crawl and index growth from filters, sorting, pagination, search, and variant URLs while preserving valuable landing pages, product discovery, and user functionality.

### Required inputs

- parameter and path inventory from routes, crawl data, logs, templates, or representative samples;
- current canonical, robots, meta robots, sitemap, and internal-link behavior;
- indexation and demand evidence when available;
- pagination and JavaScript loading model;
- business ownership and rollback path.

### Procedure

1. Inventory URL generators and normalize parameter order for analysis without changing live semantics.
2. Classify URL families by purpose: pagination, sort, filter, search, tracking/session, variant, localization, or unknown.
3. Evaluate uniqueness, search demand, conversion/business value, internal linking, canonical behavior, crawl frequency, index state, and duplication.
4. Assign a controlled action:
   - `INDEX_SELF_CANONICAL` for a genuinely distinct, valuable landing page;
   - `CRAWL_DISCOVERABLE_NOT_INDEX_TARGET` for supporting URLs that must expose products but should not become search targets;
   - `CANONICAL_TO_EQUIVALENT` only when content is duplicate or substantially equivalent;
   - `NOINDEX_CRAWLABLE` when Google must access the page to observe `noindex` and links;
   - `ROBOTS_DISALLOW` for crawl-space control only when loss of content/link access is understood;
   - `REDIRECT_OR_REMOVE` for obsolete URL families;
   - `INVESTIGATE` when evidence is insufficient.
5. Do not use robots.txt for canonicalization. Do not combine robots disallow with reliance on a page-level noindex that crawlers cannot read. For every URL family, record the combined canonical, meta robots, robots.txt, sitemap, HTTP status, and internal-link signals and flag contradictory combinations before recommending a new rule.
6. Keep paginated pages on unique URLs with crawlable `<a href>` links and self-canonicals. Do not canonicalize every page to page one.
7. For load-more or infinite-scroll UX, require crawlable paginated component URLs or another documented discovery path.
8. Model impact, rollout, monitoring, and rollback. Require owner approval for high-volume indexation changes.

### Output

- URL-family inventory and evidence coverage;
- governance decision table;
- predicted discovery/indexation consequences;
- rollout, monitoring, and rollback plan;
- unresolved risks and owner approvals.

### Hard blockers

- no representative URL evidence;
- proposed rule could remove valuable discovery or indexable demand pages without measurement;
- JS facets have no crawlable product-discovery path;
- conflicting canonical, noindex, robots, sitemap, or internal-link signals are unresolved.

---

## Skill: `agentic-commerce-readiness-check`

### Purpose

Assess foundational commerce readiness and current Google Universal Commerce Protocol readiness without misrepresenting UCP as an organic ranking factor or universal merchant requirement.

### Required inputs

- store root and checkout architecture;
- Merchant Center status and approved account evidence when available;
- target country and eligible Google surface;
- current Google UCP documentation and implementation availability;
- merchant security, payment, privacy, and legal owners.

### Procedure

1. Confirm foundations: accurate product pages, product data, Merchant Center participation where required, stable identifiers, price/availability synchronization, shipping/returns, checkout reliability, security, privacy, and support ownership.
2. Verify the current UCP implementation model, merchant eligibility, waitlist/approval status, Merchant Center prerequisites, supported capabilities, implementation path, and any account-level reporting context from Google primary documentation. UCP is a current Google commerce protocol, but access, capabilities, and supported surfaces remain context-dependent.
3. Check account-exposed UCP eligibility or reporting context only when approved account evidence exists.
4. Classify each item as `FOUNDATIONAL_REQUIRED`, `UCP_PREREQUISITE`, `UCP_OPTIONAL_CAPABILITY`, `NOT_APPLICABLE`, or `UNKNOWN`.
5. State clearly that UCP can enable direct purchase capabilities on supported Google AI surfaces, while Google says the Native integration does not influence product-listing ranking.
6. Route payment authorization, credentials, fraud, privacy, checkout, consumer law, and operational support to their accountable owners.

### Output

- foundational readiness result;
- current UCP applicability and evidence;
- prerequisites, optional capabilities, blockers, and owner map;
- implementation decision: `NOT_APPLICABLE`, `MONITOR`, `PREPARE`, `ELIGIBLE_TO_APPLY`, or `APPROVED_TO_IMPLEMENT`;
- no-ranking-guarantee statement and re-verification date.

### Failure and fallback

If current documentation or merchant eligibility cannot be verified, return `PARTIAL` or `BLOCKED`. Recommend only durable foundational work and a dated recheck. Do not invent a well-known URL requirement or other implementation detail not present in the current specification.
