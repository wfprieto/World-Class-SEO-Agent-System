# SEO Vertical Architecture Profiles

Six profiles that shape how an audit or plan is run once the business model is known: **generic**, **ecommerce**, **local-service**, **saas**, **publisher**, **agency**.

## One detection authority, one router

Business-type detection rules live in **`docs/plugin-packaging.md` section 9** and nowhere else. This file consumes that decision; it does not restate the detection rules and it is **not a second router**. `runtime/routing.py` remains the only request router. The machine-readable profile data is `scripts/vertical_profiles.py`.

Detection is a routing aid, not a factual claim about the business. A user override always wins over auto-detection.

## Confidence and ambiguity

- **Low confidence never silently routes.** With no strongly-evidenced profile, the route is `UNCONFIRMED`, and the action is to ask the owner or stop. An audit must not proceed on a guessed business model.
- **Two or more strongly-evidenced models produce a declared `HYBRID` route.** The hybrid is stated in the output, never resolved silently to whichever profile matched first.
- A single weak signal (for example the presence of a blog) does not classify a site.
- A profile is "strongly evidenced" only at two or more of its strong signals.

## Common contract

Every profile declares: detection signals, required agents, required skills, default modules, excluded or optional modules, evidence requirements, site architecture, keyword and content architecture, technical priorities, conversion model, schema considerations, GEO/AIO considerations, local or marketplace considerations where applicable, measurement model, risk conditions, handoffs, expected outputs, and stop conditions. All agent and skill names are the canonical identifiers from `agents/AGENT_INDEX.md` and `skills/SKILL_INDEX.md`.

---

## generic

The fallback when no other profile is strongly evidenced. It assumes nothing: no commerce layer, no local layer, no declared conversion. Its first job is to make the owner state the business model and the primary action. **Stop condition:** business model undeclared and unresolvable. Agents: SEO Technical, Content, Full Audit/Analyst. Modules: technical, content, indexation, CWV, schema.

## ecommerce

Signals: cart, checkout, product schema, add-to-cart, merchant feed. Architecture is category → subcategory → product with governed facets and canonical variants. Priorities: faceted crawl control, variant canonicals, hero-image LCP. Schema: Product, Offer, ProductGroup. Conversion: add-to-cart and checkout. Risks: index bloat from facets, thin variant pages, feed-versus-page mismatch. Marketplace intelligence is optional and only with a connected, cost-approved source. Excluded: local-pack. **Stop condition:** no product data source of truth. Agent: SEO E-commerce Agent.

## local-service

Signals: NAP block, store locator, LocalBusiness schema, service area, Business Profile. Service × location pages only where a real service area exists. Priorities: LocalBusiness schema, NAP consistency, mobile UX. Conversion: call, booking, directions, quote. Risks: fake locations, fake reviews, doorway city pages — all forbidden. Geo-grid rank and GBP audit need a connected, cost-approved source. Excluded: faceted-nav. **Stop condition:** no verifiable physical or service-area presence. Agent: Local SEO Agent.

## saas

Signals: pricing tiers, free trial, SoftwareApplication schema, docs site, changelog. Architecture: product → use case → integration → comparison → docs. Priorities: server-side rendering of primary content (client-only content is invisible to non-rendering crawlers), docs indexation, CWV. Conversion: trial, demo, signup. Risks: CSR content invisible to crawlers; unfair or unverifiable competitor claims — route comparative claims to the SEO Compliance & Legal Agent. Excluded: local-pack. **Stop condition:** comparison claims cannot be substantiated.

## publisher

Signals: Article schema, author bylines, high article volume, ad slots, subscription wall. Topic hubs with authored articles, clean archives and pagination. Priorities: archive indexation, CWV with ad slots, pagination. Schema: Article, NewsArticle, Person. Conversion: subscription, newsletter, ad revenue per session. Risks: content decay, ad-driven CWV regressions, thin syndicated content. Excluded: faceted-nav, local-pack. **Stop condition:** no author accountability for YMYL topics.

## agency

Signals: case studies, contact-sales, services pages, client logos. Architecture: service pages → proof → contact path. Keywords: service + industry + outcome, bottom-funnel first. Conversion: contact-sales, proposal, booked call. Risks: unverifiable results claims; thin service × city pages. Excluded: faceted-nav. **Stop condition:** claimed results cannot be evidenced.

---

## Hybrid routing

A store with physical branches is `ecommerce` + `local-service`, declared. A SaaS company with a large editorial blog is not automatically `publisher`: a blog alone is a weak signal. Require two or more strong signals per profile before a profile joins the hybrid.

## Measurement caution

Every profile's measurement model uses observed first-party data. None of these profiles, modules, or thresholds are Google metrics or ranking factors. They are kit routing and governance heuristics.
