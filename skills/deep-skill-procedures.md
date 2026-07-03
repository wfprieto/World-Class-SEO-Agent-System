# Deep Skill Procedures

These procedures add tool-aware operating depth to the original grouped skills. They are written for teams using exports, APIs, crawlers, analytics, and code inspection. When live tool access is unavailable, use verified exports and mark confidence accordingly.

## full-site-audit

Time estimate: 4-16 hours depending on site size.

1. Confirm business model, target markets, primary conversion actions, CMS/framework, and code access.
2. Collect GSC, GA4, crawl export, sitemap, robots.txt, server log sample, PageSpeed/Lighthouse data, backlink summary, rank tracking, and top competitor list.
3. Run the crawler with JavaScript rendering when the site depends on client-side routing or hydration.
4. Segment URLs by template, intent, indexability, traffic, conversion, and crawl depth.
5. Score technical, content, IA, authority, local/international, accessibility, CRO, and GEO/AIO readiness.
6. Convert findings into prioritized actions with owner, acceptance criteria, verification method, and follow-up trigger.

Decision points: escalate to SEO Technical Agent for indexation or rendering defects; SEO Copywriter/Content Agent for quality gaps; SEO Compliance & Legal Agent for regulated claims; Negative SEO & Security Agent for hacked/spam signals.

Failure handling: if first-party data is missing, complete a crawl-first audit and label traffic conclusions as low confidence.

## technical-audit

Time estimate: 2-8 hours.

1. Crawl canonical URLs, non-canonical variants, XML sitemaps, and important landing page samples.
2. Compare HTTP status, indexability, canonical, robots, noindex, hreflang, pagination, structured data, and rendered DOM.
3. Pull GSC indexing/page experience data or user-provided export.
4. Inspect template code for metadata, route generation, redirects, image handling, and sitemap generation.
5. Prioritize defects by template scale, revenue risk, crawl impact, and reversibility.

Decision points: block deployment for sitewide robots, noindex, canonical, redirect, or rendering regressions.

Failure handling: if crawl and GSC disagree, inspect live URL, rendered HTML, and GSC URL Inspection when available.

## crawl-map

Time estimate: 1-4 hours.

1. Ingest crawler export with URL, status, indexability, canonical, title, H1, depth, inlinks, outlinks, and sitemap inclusion.
2. Build sections by directory, template, content type, and search intent.
3. Identify orphan candidates, deep pages, redirected links, broken links, blocked pages, and thin duplicate groups.
4. Compare crawl discoverability against XML sitemap and top organic landing pages.
5. Produce a crawl map summary with high-value pages that need stronger internal links.

Decision points: if valuable pages are deeper than three clicks, route to SEO Information Architecture Agent.

Failure handling: if JavaScript links are missing in raw crawl, repeat with rendering enabled or inspect DOM manually.

## indexation-reality-check

Time estimate: 1-3 hours.

1. Compare intended indexable URLs against crawl export, sitemap, canonical tags, robots directives, and GSC indexing export.
2. Sample critical URLs with live URL checks where available.
3. Identify mismatches: submitted not indexed, indexed but excluded from sitemap, canonicalized unexpectedly, blocked by robots, noindexed, or soft 404.
4. Separate technical blockers from quality or duplication signals.
5. Recommend exact remediation and revalidation timing.

Decision points: prioritize pages with impressions, revenue value, or strategic topical importance.

Failure handling: if GSC data is unavailable, label conclusions as technical eligibility rather than confirmed indexation.

## schema-detect-validate-generate

Time estimate: 1-5 hours.

1. Extract JSON-LD, Microdata, and RDFa from representative templates.
2. Validate syntax locally and with rich result tooling where possible.
3. Compare schema type to page purpose, visible content, and policy eligibility.
4. Check required and recommended fields, entity consistency, sameAs references, author/publisher identity, and breadcrumbs.
5. Generate corrected JSON-LD only when it matches visible page content.
6. Add acceptance criteria for validation, rendering, and deployment.

Decision points: route medical, legal, financial, review, product, or claim-heavy schema to compliance review.

Failure handling: if validation APIs are unavailable, use local JSON-LD parsing and official schema requirements.

## core-web-vitals-triage

Time estimate: 1-6 hours.

1. Collect CrUX/PageSpeed/Lighthouse data plus field analytics if available.
2. Separate field data from lab data and mobile from desktop.
3. Identify failing LCP, INP, and CLS by template and device.
4. Inspect likely causes: server response, render-blocking resources, image sizing, script work, hydration, ads, embeds, fonts, and layout shifts.
5. Rank fixes by user impact, template scale, engineering effort, and regression risk.

Decision points: do not treat passing Lighthouse alone as success when field data fails.

Failure handling: if field data is unavailable, use lab data as diagnostic evidence only.

## seo-drift-monitor

Time estimate: 1-3 hours to configure, then recurring.

1. Define watched URLs, templates, sitemap files, robots.txt, schema types, redirects, and top queries.
2. Set baselines for indexability, status codes, titles, canonicals, CWV, rankings, clicks, and conversions.
3. Configure alerts for critical changes, material drops, and unexpected new URL patterns.
4. Assign owner and response SLA by severity.
5. Log drift events and remediation outcomes.

Decision points: route security-like drift to Negative SEO & Security Agent immediately.

Failure handling: tune alert thresholds when false positives exceed useful signal.

## content-brief

Time estimate: 1-3 hours.

1. Confirm audience, funnel stage, target query set, business goal, and content type.
2. Review SERP intent, competitor structures, People Also Ask, related entities, and first-party performance data.
3. Define information gain, required expertise, proof points, internal links, metadata, schema, and conversion path.
4. Produce outline, heading logic, FAQs, media needs, and source requirements.
5. Add acceptance criteria for originality, usefulness, readability, compliance, and measurement.

Decision points: reject briefs that only repackage competitor summaries without unique value.

Failure handling: if SERP access is unavailable, use supplied keyword/topic data and mark SERP confidence low.

## content-audit

Time estimate: 2-8 hours.

1. Export URLs with traffic, impressions, rankings, conversions, publish date, update date, word count, and content type.
2. Classify each page as keep, improve, consolidate, redirect, noindex, or retire.
3. Compare content against intent, information gain, E-E-A-T, internal links, freshness, duplication, and conversion fit.
4. Group recommendations by template and business value.
5. Define measurement windows and post-change tracking.

Decision points: do not delete or redirect pages with meaningful assisted conversion value without stakeholder approval.

Failure handling: if conversion data is missing, use traffic and intent as provisional signals.

## content-decay

Time estimate: 1-4 hours.

1. Compare 3, 6, and 12-month trends for clicks, impressions, average position, conversions, and engagement.
2. Separate seasonality from ranking decay, SERP feature shifts, cannibalization, and outdated content.
3. Identify lost queries and missing subtopics.
4. Recommend refresh, consolidation, technical fix, or no action.
5. Set recheck date after recrawl and indexing.

Decision points: route template-wide drops to SEO Technical Agent before rewriting content.

Failure handling: if historical data is short, classify as early signal rather than decay.

## keyword-cluster

Time estimate: 1-5 hours.

1. Collect keywords, questions, entities, intent, search volume, difficulty, current ranking URL, and SERP similarity.
2. Group by shared intent and page eligibility, not only word overlap.
3. Map each cluster to new page, existing page, section, FAQ, or no-build decision.
4. Identify cannibalization and internal link requirements.
5. Prioritize by business value, conversion intent, and ability to satisfy searcher need.

Decision points: create separate pages only when SERPs and user needs are materially different.

Failure handling: if volume data is absent, use qualitative intent and first-party query data.

## sxo-page-fit

Time estimate: 1-3 hours.

1. Identify page intent, organic queries, user task, conversion goal, and current CTA.
2. Review above-the-fold clarity, answer completeness, trust signals, accessibility, speed, and friction.
3. Compare CTA language to query intent and funnel stage.
4. Recommend UX, copy, trust, and measurement improvements.
5. Define test hypothesis when changes could affect revenue.

Decision points: route high-risk funnel changes to SEO CRO Agent and human approval.

Failure handling: if behavior data is missing, frame recommendations as UX heuristics.

## internal-link-map

Time estimate: 1-6 hours.

1. Ingest crawl inlinks/outlinks, sitemap, organic landing pages, topic clusters, and priority URLs.
2. Identify orphan pages, deep pages, over-linked low-value pages, broken links, and anchor text mismatches.
3. Map hub, spoke, sibling, breadcrumb, contextual, and footer/header link roles.
4. Recommend link additions/removals with source URL, target URL, anchor, placement, and reason.
5. Validate that links are crawlable HTML links and do not create confusing user paths.

Decision points: route taxonomy or navigation changes to SEO Information Architecture Agent.

Failure handling: if crawler misses rendered links, inspect raw HTML and rendered DOM.

## local-seo-audit

Time estimate: 2-6 hours per market group.

1. Collect GBP data, citations, reviews, local landing pages, NAP, categories, photos, products/services, and local rankings.
2. Compare consistency across website, GBP, citations, schema, and maps.
3. Review local landing page uniqueness, service area clarity, driving directions, reviews, and conversion paths.
4. Identify duplicate listings, category issues, review risks, and citation gaps.
5. Prioritize actions by local pack impact and business importance.

Decision points: escalate legal or reputation-sensitive review responses before publication.

Failure handling: if GBP access is unavailable, audit public listing evidence and request owner access.

## hreflang-audit

Time estimate: 1-6 hours.

1. Export all locale URLs with canonicals, status, indexability, language/country, and hreflang annotations.
2. Validate reciprocal links, x-default, self-references, valid ISO codes, and canonical alignment.
3. Compare language targeting to sitemap and site architecture.
4. Sample rendered pages for language mismatch and machine-translation risk.
5. Produce fix map by template or locale.

Decision points: hreflang should not point to redirected, noindexed, blocked, or non-canonical URLs.

Failure handling: if locale inventory is incomplete, audit highest-value markets first.

## image-seo-audit

Time estimate: 1-4 hours.

1. Crawl images with URL, status, format, dimensions, file size, alt text, lazy loading, and page context.
2. Review filenames, alt text usefulness, image compression, responsive variants, and indexability.
3. Check image sitemap or media inclusion where relevant.
4. Identify images that deserve unique landing context for visual search.
5. Recommend fixes by template.

Decision points: decorative images need empty alt text; meaningful images need specific accessible descriptions.

Failure handling: if image assets are CDN-transformed, inspect final rendered URLs.

## video-seo-audit

Time estimate: 1-4 hours.

1. Inventory videos, host platform, embed method, transcripts, captions, thumbnails, titles, descriptions, and schema.
2. Validate VideoObject fields, thumbnail access, upload date, duration, and transcript availability.
3. Check if important videos have crawlable surrounding copy and clear page purpose.
4. Recommend timestamp chapters, transcript improvements, schema fixes, and sitemap inclusion.
5. Map video assets to search intent and conversion path.

Decision points: avoid schema claims that are not visible or accessible on the page.

Failure handling: if platform data is unavailable, audit public embeds and page source.

## geo-aio-citation-audit

Time estimate: 2-6 hours.

1. Identify priority questions, entities, definitions, comparisons, and decision queries.
2. Capture AI search and SERP citation snapshots where permitted.
3. Review content for concise answers, entity clarity, citations, author credibility, originality, and structured summaries.
4. Compare brand/entity consistency across site, profiles, schema, and trusted references.
5. Recommend content and technical changes that improve citation eligibility without manipulating systems.

Decision points: route unsupported claims to SEO Compliance & Legal Agent.

Failure handling: AI answers vary; use repeated snapshots and label volatility.

## knowledge-graph-sync

Time estimate: 1-4 hours.

1. Inventory organization, person, product, place, and service entities.
2. Compare site schema, About/contact pages, sameAs links, GBP, social profiles, Wikidata/Crunchbase-like sources where applicable, and brand SERP.
3. Resolve name, address, logo, founder, product, and relationship inconsistencies.
4. Recommend schema and profile updates with source of truth.
5. Track confirmation after recrawl and SERP refresh.

Decision points: do not invent entity relationships or credentials.

Failure handling: if third-party profiles cannot be edited, document discrepancy and owner.

## backlink-profile

Time estimate: 1-5 hours.

1. Export backlinks from available tools and GSC/Bing where possible.
2. Classify links by authority, topical relevance, anchor, follow/nofollow, landing page, country, and risk.
3. Identify toxic patterns, sudden spikes, lost links, broken targets, and high-value opportunities.
4. Separate disavow candidates from low-quality links that should simply be monitored.
5. Recommend defensive, recovery, and authority-building actions.

Decision points: disavow requires strong evidence and human approval.

Failure handling: if backlink tools disagree, focus on patterns confirmed by more than one source.

## backlink-gap

Time estimate: 2-6 hours.

1. Select true organic competitors by topic and SERP overlap.
2. Export competitor referring domains, linked pages, anchors, and content types.
3. Identify links competitors have that the site plausibly deserves.
4. Classify opportunities as PR, resource page, partnership, citation, broken link, or content asset.
5. Prioritize by relevance, authority, likelihood, and brand safety.

Decision points: reject paid, manipulative, irrelevant, or private-network opportunities.

Failure handling: if competitor data is incomplete, use sample-based opportunity mapping.

## seo-roadmap

Time estimate: 2-8 hours.

1. Collect findings, business goals, team capacity, release cadence, budget, and risk tolerance.
2. Group work into technical fixes, content improvements, IA changes, authority building, monitoring, and experiments.
3. Score impact, effort, confidence, risk, dependency, and time-to-value.
4. Build 30/60/90-day plan and quarterly themes.
5. Assign owners, acceptance criteria, reporting cadence, and follow-up triggers.

Decision points: prioritize blockers and measurement setup before speculative growth work.

Failure handling: if business priorities are unclear, create scenario-based roadmap options.

## prioritization-matrix

Time estimate: 1-3 hours.

1. Normalize all candidate actions into comparable units.
2. Score SEO impact, business impact, confidence, effort, risk, reversibility, and dependency.
3. Identify P0 blockers, P1 high-impact fixes, P2 improvements, and P3 backlog.
4. Challenge outlier scores with the Scrummaster Agent.
5. Publish decision record for material tradeoffs.

Decision points: do not let easy tasks outrank critical indexation or revenue risks.

Failure handling: if data is weak, lower confidence and add evidence-gathering task.

## scrummaster-debate

Time estimate: 30-90 minutes.

1. State the decision, stakes, options, and non-negotiable constraints.
2. Assign agents to defend, challenge, and risk-test the options.
3. Require evidence, assumptions, failure modes, and rollback plans.
4. Resolve conflicts through impact, confidence, reversibility, and user benefit.
5. Record final decision, dissent, owner, and follow-up.

Decision points: use debate for sitewide, high-cost, high-risk, or ambiguous SEO choices.

Failure handling: if evidence is insufficient, pause implementation and request the missing data.

## experiment-design

Time estimate: 1-4 hours.

1. Define hypothesis, page group, expected mechanism, metric, guardrail, and minimum detectable effect.
2. Choose test design: SEO split test, time-series, phased rollout, or controlled content update.
3. Confirm sample size, seasonality, indexing lag, and confounding changes.
4. Set analysis window and decision rule before launch.
5. Record outcome and reusable learning.

Decision points: avoid tests that risk critical revenue pages without approval.

Failure handling: if test cannot be isolated, classify as observational learning.

## knowledge-sync

Time estimate: 1-3 hours per update cycle.

1. Monitor official search documentation, status dashboards, AI search guidance, standards, and trusted industry experiments.
2. Convert findings into rule updates with source, old assumption, new instruction, target agent, and validation check.
3. Reject rumors that lack primary source or repeatable evidence.
4. Update knowledge files and notify affected agents.
5. Schedule revalidation for rules with uncertain impact.

Decision points: official documentation overrides anecdotal advice unless contradicted by direct first-party evidence.

Failure handling: if guidance is ambiguous, create a cautious provisional rule.

## compliance-review

Time estimate: 1-4 hours.

1. Identify jurisdiction, industry, regulated claims, data collection, affiliate/sponsored content, and user-generated content.
2. Review copy, schema, disclosures, testimonials, privacy/cookie behavior, author credentials, and AI-generated content statements.
3. Flag risky claims, missing disclosures, unsupported superlatives, trademark issues, and policy conflicts.
4. Recommend safer language and escalation needs.
5. Require human legal/compliance approval for regulated or high-risk changes.

Decision points: compliance risk overrides ranking opportunity.

Failure handling: if legal context is unknown, mark recommendations as requiring counsel review before publication.
