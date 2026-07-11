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

## seo-diagnostic-stack-design

Time estimate: 1-4 hours.

1. Ask for monthly tool budget, site type, CMS/framework, code access, analytics access, GSC/Bing access, reporting audience and monitoring needs.
2. Define the free baseline first: GSC, Bing Webmaster Tools, GA4, PageSpeed Insights, Rich Results Test, Looker Studio and crawl exports where possible.
3. Map paid tools only to clear jobs: crawler, rank tracking, backlink data, local listings, AI search visibility, reporting or enterprise monitoring.
4. Document setup owner, credentials owner, data refresh cadence, alert thresholds and report recipients.
5. Create the diagnostic scorecard and mark any unavailable data as missing rather than clean.

Decision points: recommend paid tools only when site size, reporting burden, revenue value or technical risk justifies them.

Failure handling: if budget is unknown, provide free, low-budget and growth-budget options.

## sitemap-audit

Time estimate: 30 minutes to 3 hours.

1. Collect XML sitemap index, child sitemaps, CMS sitemap settings and submitted sitemap data from GSC/Bing when available.
2. Validate status codes, canonical targets, indexability, robots access, lastmod accuracy and URL count.
3. Compare sitemap URLs against crawl-discovered URLs, priority landing pages and excluded URLs.
4. Remove redirected, blocked, noindexed, duplicate, parameter and non-canonical URLs.
5. Confirm the sitemap only lists URLs the site wants indexed.

Decision points: route sitemap generation defects to Senior SEO Engineer Agent when they come from code or CMS templates.

Failure handling: if GSC access is missing, validate sitemap eligibility through crawl and live HTTP checks.

## score-normalization

Time estimate: 30-90 minutes.

1. Collect raw scores from audits, tools and agent outputs.
2. Normalize each score to the repository scoring model so severity is comparable across technical, content, local, authority and risk categories.
3. Weight issues by business impact, affected URL count, confidence, risk and reversibility.
4. Separate health scores from opportunity scores.
5. Explain scoring limits in plain language.

Decision points: do not average critical risks into a harmless-looking overall score.

Failure handling: if a tool score lacks methodology, use it as supporting context only.

## technical-implementation

Time estimate: 1-8 hours depending on codebase complexity.

1. Identify the template, route, component, CMS setting or build process causing the SEO issue.
2. Make the smallest code or configuration change that fixes the behavior.
3. Add or update tests for metadata, schema, sitemaps, redirects, robots, canonicals, image handling or rendered output.
4. Validate locally through rendered HTML, HTTP response, build output and crawler-like checks.
5. Document rollback path and post-deploy verification.

Decision points: require approval for sitewide robots, noindex, canonical, redirect or revenue-template changes.

Failure handling: if the code owner cannot be identified, create an implementation ticket with exact files, expected output and acceptance criteria.

## redirect-validation

Time estimate: 30 minutes to 4 hours.

1. Collect redirect map, legacy URLs, target URLs, status codes, canonicals and traffic/backlink importance.
2. Test one-hop behavior, chains, loops, 404s, soft 404s, protocol/host consistency and query handling.
3. Compare target relevance to old page intent.
4. Validate that internal links and sitemaps point to final canonical URLs.
5. Prioritize fixes for high-traffic, linked or revenue-sensitive URLs.

Decision points: reject redirects that send users to irrelevant pages just to preserve link equity.

Failure handling: if legacy inventory is incomplete, combine crawl, analytics landing pages, backlinks and server logs.

## seo-ci-checks

Time estimate: 1-6 hours.

1. Identify SEO behaviors that can be tested before deployment.
2. Add checks for titles, canonicals, robots directives, schema syntax, sitemap generation, redirects, heading structure and critical rendered links.
3. Use fixture pages that represent important templates.
4. Fail builds only on clear regressions, and warn on advisory improvements.
5. Document how engineers update fixtures when templates change intentionally.

Decision points: CI should catch breakage, not become a noisy audit report.

Failure handling: if rendering is hard in CI, start with static output and add browser checks later.

## content-inventory

Time estimate: 1-6 hours.

1. Export all indexable and important non-indexable URLs with type, owner, publish date, update date, traffic, conversions, links and status.
2. Classify pages by intent, funnel stage, topic, template and target market.
3. Flag missing owners, stale pages, duplicates, thin pages and cannibalization candidates.
4. Join crawl, GSC, analytics and CMS data where possible.
5. Produce a maintainable inventory with update cadence.

Decision points: inventory must support action, not just count URLs.

Failure handling: if CMS export is missing, build the first inventory from crawl and analytics.

## metadata-generation

Time estimate: 30 minutes to 4 hours.

1. Confirm page purpose, query intent, audience, offer and differentiator.
2. Review current title, meta description, H1 and SERP competitors.
3. Write titles that are specific, accurate and naturally include the core query when appropriate.
4. Write descriptions that explain the page value without ranking promises or fake urgency.
5. Pass all visible and SERP-facing copy through `anti-ai-public-writing`.

Decision points: do not mass-generate metadata for pages with unclear intent or duplicate content.

Failure handling: if page content is weak, recommend page improvement before metadata polish.

## citation-audit

Time estimate: 1-5 hours.

1. Collect major local directories, industry directories, map listings, data aggregators and niche citation sources.
2. Compare name, address, phone, URL, hours, categories and service areas.
3. Flag duplicates, stale locations, tracking-number conflicts and inconsistent categories.
4. Prioritize citation fixes by authority, local relevance and visibility.
5. Document owner access and correction status.

Decision points: avoid creating citations on low-quality directories that add spam risk.

Failure handling: if login access is unavailable, prepare public correction requests and owner tasks.

## review-strategy

Time estimate: 1-3 hours.

1. Audit review platforms, ratings, volume, velocity, sentiment, response quality and competitor benchmarks.
2. Identify service lines, locations or staff patterns behind review themes.
3. Build compliant review request timing and messaging.
4. Draft response rules for positive, negative and sensitive reviews.
5. Define monitoring cadence and escalation path.

Decision points: never incentivize, gate or fake reviews.

Failure handling: route legal, medical, employment or harassment issues to human review.

## international-url-architecture

Time estimate: 2-8 hours.

1. Confirm markets, languages, currencies, legal requirements, inventory differences and search engines.
2. Choose subdirectory, subdomain or ccTLD approach based on operations and risk.
3. Map locale URL rules, canonicals, hreflang, x-default, redirects and language selectors.
4. Define localized content requirements and duplicate-control rules.
5. Create migration and validation plan.

Decision points: do not launch locale pages that are translated but not localized for users.

Failure handling: if markets are uncertain, start with a limited locale pilot.

## localized-content-review

Time estimate: 1-6 hours per market group.

1. Compare localized page copy against source page, local SERP intent, terminology, currency, units, laws and cultural context.
2. Check translator notes, reviewer ownership and local proof points.
3. Validate metadata, headings, internal links, schema and CTAs for the market.
4. Flag literal translations that miss local search behavior.
5. Recommend local examples, FAQs, entities and trust signals.

Decision points: localized content must satisfy the market, not just mirror the source language.

Failure handling: if no native reviewer is available, mark confidence medium or low.

## brand-serp-audit

Time estimate: 1-3 hours.

1. Capture branded search results across priority markets and devices.
2. Review site links, knowledge panel, social profiles, review sites, news, images, videos and AI answers.
3. Identify inaccurate entity facts, weak owned-asset coverage, reputation risks and missing proof sources.
4. Align schema, About page, sameAs links and third-party profiles.
5. Create fixes by owned, editable and third-party sources.

Decision points: reputation-sensitive issues need stakeholder review before response.

Failure handling: SERPs vary, so record date, location and query variants.

## conversational-query-map

Time estimate: 1-4 hours.

1. Gather questions from GSC, support tickets, sales calls, forums, People Also Ask and internal search.
2. Group questions by intent, funnel stage and answer type.
3. Map each group to existing pages, FAQs, support content or new content needs.
4. Write concise answer patterns that sound natural when spoken.
5. Add schema only when it matches visible content and policy.

Decision points: avoid creating thin FAQ blocks just to target voice search.

Failure handling: if question data is sparse, use sales/support input and mark as qualitative.

## official-source-monitor

Time estimate: 30-90 minutes per cycle.

1. Track official search engine docs, status dashboards, structured data docs, browser performance guidance and AI search platform guidance.
2. Record source, date, change type and affected agents.
3. Separate confirmed documentation from industry commentary.
4. Convert changes into rule updates or watch items.
5. Schedule follow-up validation when guidance is unclear.

Decision points: official guidance does not automatically mean immediate site changes; assess impact first.

Failure handling: if a source changes without detail, create a monitoring note rather than a new rule.

## digital-pr-asset-brief

Time estimate: 1-4 hours.

1. Identify audience, journalist angle, data source, expert voice and linkable page.
2. Validate that the asset has a real reason to earn coverage.
3. Define headline angles, proof, visuals, methodology and outreach targets.
4. Check legal, claims and data rights before publication.
5. Plan internal links from the asset to relevant commercial or educational pages.

Decision points: reject assets that exist only to ask for links without news value.

Failure handling: if proprietary data is unavailable, use expert analysis or original research.

## outreach-prospecting

Time estimate: 1-6 hours.

1. Define prospect type: journalist, editor, resource page owner, partner, association or unlinked mention owner.
2. Find relevant prospects and verify topical fit, authority, editorial standards and contact path.
3. Remove spam sites, link sellers, unrelated blogs and private networks.
4. Personalize pitch angle to the prospect's audience.
5. Track outreach status, response, link outcome and relationship notes.

Decision points: quality and relevance beat volume.

Failure handling: if contact data is uncertain, verify manually before sending.

## negative-seo-threat-review

Time estimate: 1-4 hours.

1. Monitor backlink spikes, anchor anomalies, hacked pages, scrape patterns, indexation spam and suspicious redirects.
2. Compare new risks against historical baseline.
3. Separate annoying low-quality noise from material threats.
4. Preserve evidence before requesting removal, security cleanup or disavow review.
5. Escalate malware, hacked content and injected pages immediately.

Decision points: disavow only after strong evidence and human approval.

Failure handling: if data is incomplete, monitor trend and expand evidence sources.

## security-indexation-check

Time estimate: 30 minutes to 3 hours.

1. Search indexed pages for unexpected paths, spam titles, injected languages, casino/pharma terms and rogue subdomains.
2. Compare crawl, sitemap, server logs and GSC security/manual action data.
3. Inspect suspicious URLs for status, canonical, templates and source.
4. Coordinate cleanup with engineering/security.
5. Request recrawl or removals only after root cause is fixed.

Decision points: treat indexed malware or hacked content as critical.

Failure handling: if access is limited, document public evidence and escalation owner.

## spam-policy-check

Time estimate: 1-3 hours.

1. Review content, links, redirects, programmatic pages, affiliate sections, reviews and third-party hosted content.
2. Compare tactics against current search spam policies and site reputation abuse guidance.
3. Flag scaled low-value content, cloaking, doorway pages, manipulative links and misleading structured data.
4. Recommend removal, noindex, rewrite, disclosure or governance changes.
5. Record policy source and confidence.

Decision points: policy risk overrides short-term traffic.

Failure handling: if policy fit is uncertain, route to AI Principal SEO Scientist and Compliance Agent.

## claims-risk-review

Time estimate: 30 minutes to 3 hours.

1. Extract claims about results, rankings, price, performance, credentials, health, money, legality and comparisons.
2. Match each claim to proof or approved source material.
3. Flag unsupported superlatives, guarantees, testimonials and regulated statements.
4. Rewrite risky claims into safer, accurate language.
5. Route sensitive claims to legal/compliance owner.

Decision points: never invent proof to preserve stronger copy.

Failure handling: if proof is missing, remove the claim or label it for approval.

## competitive-gap

Time estimate: 2-8 hours.

1. Identify true search competitors by SERP overlap, not only business category.
2. Compare ranking pages, content depth, templates, internal links, schema, backlinks and SERP features.
3. Find gaps where competitors satisfy intent better or own stronger authority signals.
4. Separate useful opportunities from copycat distractions.
5. Prioritize gaps by business value and realistic ability to win.

Decision points: do not chase competitor pages that do not match the business model.

Failure handling: if rank data is limited, sample priority SERPs manually.

## competitor-change-monitor

Time estimate: 1-3 hours to configure, then recurring.

1. Track competitor new pages, removed pages, title changes, schema changes, internal links, rankings, links and AI citations.
2. Set thresholds for material changes.
3. Classify changes as content, technical, authority, SERP or product positioning.
4. Trigger a response only when the change affects priority topics or markets.
5. Archive snapshots for comparison.

Decision points: monitoring should inform strategy, not create reactive busywork.

Failure handling: if crawl access is blocked, rely on SERP/rank/backlink signals.

## forecasting

Time estimate: 1-6 hours.

1. Gather historical clicks, impressions, rankings, seasonality, conversions and planned changes.
2. Segment by page group, topic, market and funnel stage.
3. Build conservative, expected and upside scenarios.
4. State assumptions, confidence and external risks.
5. Tie forecast to measurement windows and leading indicators.

Decision points: avoid precise forecasts when data is volatile or sparse.

Failure handling: if history is weak, use directional forecast with wider ranges.

## trend-monitor

Time estimate: 30-90 minutes per cycle.

1. Monitor query growth, social/search demand, news, forums, customer questions and competitor publishing.
2. Separate durable demand from short-lived noise.
3. Map trends to existing pages, new content, PR angles or no action.
4. Alert content and strategy agents before the peak when possible.
5. Track outcomes from acted-on trends.

Decision points: trend relevance must beat raw volume.

Failure handling: if data source reliability is unknown, require confirmation from a second source.

## executive-summary

Time estimate: 30-90 minutes.

1. Read the source findings, decisions and verification results.
2. Lead with what changed, what matters and what should happen next.
3. Translate technical details into business language.
4. Separate confirmed facts from expected benefits.
5. Keep the summary short enough for a busy stakeholder.

Decision points: include risk and missing evidence even when the report is positive.

Failure handling: if findings conflict, ask Scrummaster Agent for a decision record.

## plain-language-seo-report

Time estimate: 1-3 hours.

1. Gather audit results, completed work, copy changes, metadata changes, technical fixes, recommendations and verification status.
2. Translate each item into what was checked, what was changed, why it matters and what happens next.
3. Remove jargon or define unavoidable terms in one sentence.
4. Avoid ranking guarantees and unsupported benefit claims.
5. End with clear next steps, owners and follow-up timing.

Decision points: do not hide missing access, unverified changes or risks.

Failure handling: if source outputs are incomplete, list what is missing and produce a partial report.

## content-calendar

Time estimate: 1-4 hours.

1. Convert prioritized clusters, briefs, seasonality and business events into a publish/update schedule.
2. Balance new content, refreshes, technical dependencies and promotional timing.
3. Assign owner, draft date, review date, publish date and measurement date.
4. Add proof/source requirements and compliance checkpoints.
5. Keep capacity realistic.

Decision points: do not schedule more content than the team can make useful.

Failure handling: if resources are unknown, create a minimum viable calendar.

## request-routing

Time estimate: 5-20 minutes.

1. Read the request for primary intent, risk, evidence needs and likely output.
2. Choose one lead agent and only necessary support agents.
3. Identify required evidence and missing access.
4. Select workflow and approval gates.
5. Record routing confidence and escalation trigger.

Decision points: high-risk or unclear requests should route through SEO Scrummaster Agent.

Failure handling: if the request is vague, start with the least risky discovery workflow.

## decision-record

Time estimate: 15-45 minutes.

1. State the decision, date, owner, context and options considered.
2. Record evidence, assumptions, dissent and risk.
3. Explain why the chosen path beat alternatives.
4. Define acceptance criteria, rollback and follow-up.
5. Link related agent outputs and tickets.

Decision points: create records for sitewide, high-risk, expensive or contested decisions.

Failure handling: if no decision was made, record open questions instead.

## definition-of-done

Time estimate: 15-45 minutes.

1. Define what must be true in code, content, analytics, crawl data and stakeholder approval.
2. Include acceptance criteria, verification method, owner and timing.
3. Add rollback or monitoring requirements for risky changes.
4. Distinguish launch done from SEO validated.
5. Confirm evidence source for each criterion.

Decision points: a task is not done just because it was published.

Failure handling: if verification access is missing, mark the item blocked or conditionally done.

## anti-ai-public-writing

Time estimate: 10-90 minutes depending on copy volume.

1. Identify the visitor-facing placement, audience, page intent and action the text should support.
2. Check every claim against supplied proof.
3. Remove obvious AI phrasing, hype, generic SEO filler, stiff openers, em dashes and mechanical rhythm.
4. Rewrite for plain speech, specificity and natural flow.
5. Preserve useful brand personality without making the copy sound like a press release.
6. Recheck SEO terms so they fit naturally.

Decision points: if proof is missing, weaken or remove the claim rather than dressing it up.

Failure handling: route regulated, legal, medical, financial, pricing or guarantee claims to compliance review.

## analytics-synthesis

Time estimate: 1-4 hours.

1. Pull GSC, GA4, rank, crawl and conversion data into one page/topic view.
2. Separate traffic, visibility, engagement and conversion signals.
3. Identify where data agrees, where it conflicts and where tracking is missing.
4. Translate metrics into findings with evidence references and confidence.
5. Route technical drops, content decay, CRO issues or measurement gaps to the right agent.

Decision points: do not treat traffic loss as an SEO cause until tracking, seasonality and technical changes are checked.

Failure handling: if analytics access is missing, use available exports and mark confidence lower.

## accessibility-audit

Time estimate: 1-6 hours.

1. Review headings, labels, alt text, keyboard access, focus order, forms and screen reader cues.
2. Run Lighthouse, axe/WAVE-style checks or supplied accessibility exports.
3. Compare accessibility defects against SEO impact, user impact and implementation effort.
4. Flag missing alt text, broken heading order, unlabeled controls and inaccessible content that searchers need.
5. Produce fixes with acceptance criteria and verification method.

Decision points: prioritize blockers that prevent users or crawlers from understanding primary content.

Failure handling: if automated tooling is unavailable, inspect templates manually and mark coverage limits.

## conversion-intent-map

Time estimate: 1-3 hours.

1. Map organic queries to funnel stage, user intent and expected next action.
2. Compare current CTA, offer and page format against that intent.
3. Identify mismatch between informational, commercial, local and transactional visitors.
4. Recommend CTA, trust proof, internal link and content changes.
5. Define measurement plan for conversion movement.

Decision points: do not push aggressive CTAs on pages where users still need education or proof.

Failure handling: if conversion data is missing, use intent analysis and flag need for analytics setup.

## landing-page-cro-audit

Time estimate: 1-5 hours.

1. Review organic landing pages by traffic, query intent, engagement, conversions and business value.
2. Inspect above-the-fold message, CTA clarity, proof, speed, accessibility and friction.
3. Compare page promise against SERP intent and metadata.
4. Identify testable changes and guardrail metrics.
5. Recommend changes with risk level and stop conditions.

Decision points: require approval before changing revenue-critical pages or lead forms.

Failure handling: if heatmap/session data is absent, use heuristic audit and analytics exports.

## local-landing-page-brief

Time estimate: 1-3 hours per page type.

1. Confirm location, service area, services, proof points, reviews, staff, photos and local regulations.
2. Research local query intent and competing local landing pages.
3. Define unique local value, NAP, map embed, driving/service details, FAQs and internal links.
4. Add GBP, citation and schema requirements.
5. Pass public-facing copy through `anti-ai-public-writing`.

Decision points: do not create fake or doorway location pages.

Failure handling: if local proof is missing, produce a content brief that asks for real evidence before drafting.

## regional-keyword-map

Time estimate: 1-4 hours per market group.

1. Gather regional query data, language variants, local terminology and search engine differences.
2. Group queries by market, language, intent and page eligibility.
3. Map clusters to existing pages, localized pages or no-build decisions.
4. Identify hreflang, currency, units, spelling and compliance needs.
5. Prioritize by business value, search demand and localization readiness.

Decision points: region-specific pages need distinct user value, not only swapped city or country names.

Failure handling: if market data is sparse, use GSC country filters, sales input and regional SERP samples.

## product-page-seo-audit

Time estimate: 1-3 hours per template.

1. Confirm page type; redirect non-product URLs. Prefer rendered HTML (see rendered-visual-audit) because many stores hydrate client-side.
2. Score title, metadata, headings, product content uniqueness (not manufacturer copy-paste), specs table, and on-page reviews.
3. Score images: descriptive alt/filenames, modern format, hero >= 800px for Shopping, AI-image labeling (knowledge/ai-image-labeling.md).
4. Delegate schema to product-schema-validate-generate and hero-image LCP to core-web-vitals-triage.
5. Weighted score /100: schema 25, title/meta 15, images 20, content 20, internal links 10, technical 10.

Decision points: escalate pricing/claims to SEO Compliance & Legal Agent; escalate faceted crawl to SEO Technical Agent. Failure handling: if only source HTML is available, flag rendered/visual checks as skipped.

## product-schema-validate-generate

Time estimate: 30-90 minutes.

1. Load knowledge/schema-deprecation-registry.md and reject deprecated types before generating.
2. Validate required Product/Offer fields (price numeric no symbol, ISO 4217 currency, full availability enum, brand, seller).
3. Recommend ProductGroup with hasVariant/variesBy for variant families instead of duplicate Product blocks.
4. Add aggregateRating/review only when genuine and visible. No self-serving review markup.
5. Output corrected JSON-LD and a completeness score.

Decision points: block generation when markup would describe hidden or fabricated content. Failure handling: return the registry replacement when a requested type is dead.

## marketplace-intelligence

Time estimate: 1-2 hours (requires a connected metered source).

1. Detect a live marketplace source; if none, report unavailable and stop. Never fabricate prices, sellers, or share.
2. Show a cost estimate and get approval before every metered call.
3. Pull pricing distribution, seller landscape, and listing-quality benchmarks; compare Google Shopping vs Amazon where available.
4. Log actual cost consumed.

Decision points: fall back to on-page and schema analysis when no source is connected. Failure handling: on rate limit or budget stop, report and halt.

## marketplace-keyword-gap

Time estimate: 1-2 hours (requires connected sources).

1. Pull organic ranked keywords for the domain.
2. Pull Shopping presence for the top organic keywords.
3. Classify each keyword: Organic Only, Shopping Only, Both, Neither, with a recommended action.

Decision points: run whichever channel is connected and mark the other unavailable. Failure handling: no fabricated volumes or CPCs.

## faceted-navigation-governance

Time estimate: 2-4 hours.

1. Classify each filter/sort/variant parameter: indexable-valuable, canonical-to-base, or block-from-crawl.
2. Recommend self-referencing canonicals on primary categories; canonicalize sorted/filtered views to base.
3. Recommend robots disallow or noindex for combinatorial facets; keep high-demand facet pages indexable with unique content.
4. Hand crawl-budget monitoring to SEO Technical Agent.

Decision points: never block valuable demand pages. Failure handling: request live faceted URLs or a crawl export when patterns are JS-only.

## merchant-data-consistency-audit

Time estimate: 1-2 hours (requires page and feed/account evidence).

1. Match the exact product and variant across page, structured data, feed, checkout-accessible state, and any approved marketplace source.
2. Reconcile price, availability, title, GTIN/MPN/SKU, image, and shipping/return fields; preserve every conflict rather than choosing the convenient value.
3. Report a consistency matrix and flag Merchant Center disapproval risks. Mandatory when both page and merchant/feed evidence exist.

Decision points: hand feed-pipeline fixes to the data/engineering owner. Failure handling: run with partial evidence only to establish missing reconciliation fields, and label coverage.

## agentic-commerce-readiness-check

Time estimate: 30-60 minutes.

1. Confirm foundational readiness: clean Product/Offer schema, valid Merchant feed, accurate business profile.
2. Note whether an agent-commerce capability profile exists; report presence as opportunity, absence as neutral.
3. Verify the current standard and its canonical URL against a Google primary source before recommending implementation.

Decision points: separate confirmed foundations (FACT) from speculative readiness (HYPOTHESIS). Failure handling: recommend only the foundational work that pays off regardless.

## programmatic-seo-governance

Time estimate: 4-12 hours depending on page count.

1. Define the page-set thesis and audit the data foundation (provenance, freshness, null/duplicate rates).
2. Build the intent/entity map; flag doorway-like or duplicate-intent clusters as hard stops.
3. Test a stratified sample per template family (at least 30 rendered pages when the population permits).
4. Measure similarity with multiple diagnostics; apply gates: warn at 30 near-duplicate pages, hard stop at 50; warn below 60% unique, hard stop below 40%.
5. Govern URLs, canonicals, robots, sitemaps; issue a launch decision (APPROVED_CANARY, APPROVED_STAGED, HOLD_FOR_REWORK, BLOCKED) with progressive rollout.

Decision points: no agent overrides a hard stop; escalate exceptions per the skill. Failure handling: on missing data or rendered samples, return PARTIAL/BLOCKED, never inferred approval.

## geo-grid-rank-scan

Time estimate: 30-90 minutes (requires a connected metered maps-SERP source).

1. Confirm a Tier 1 source is connected; if not, report unavailable and stop.
2. Geocode the business center; generate grid points with the Haversine offset (default 7x7, 5 km).
3. Show a cost estimate and get approval before firing one query per grid point.
4. Compute Share of Local Voice, average rank, and weakest quadrant; render an ASCII heatmap.

Decision points: never estimate ranks without a source. Failure handling: offer competitor-radius-map at the free tier when rank data is unavailable.

## gbp-profile-audit

Time estimate: 45-90 minutes.

1. Prefer live profile data (Tier 1); score the ~25 ranking-relevant fields (present-and-optimized 2, present 1, missing 0), apply industry weights, normalize to 100.
2. At the free tier, score detectable on-site signals and mark the rest unknown.
3. Never recommend keyword-stuffing the business name or fake categories.

Decision points: label all unknowns. Failure handling: provide the static 25-field checklist for manual completion.

## competitor-radius-map

Time estimate: 30-60 minutes.

1. Geocode the center. At the free tier, query an open POI source for same-category businesses in radius.
2. At Tier 1, use the maps-SERP source for keyword+location and extract competitors with rating, reviews, categories, density.
3. Present a competitor landscape table; distinguish presence (free) from rank (metered).

Decision points: no invented ratings. Failure handling: widen radius or broaden category and say what changed.

## cross-platform-nap-verify

Time estimate: 30-60 minutes.

1. Retrieve NAP from each available platform (Google, Bing, Apple, OSM).
2. Compare each field: exact, partial, missing, or conflicting.
3. Severity: name mismatch Critical, address High, phone Medium; recommend claiming unclaimed profiles.

Decision points: report conflicts, do not silently pick one. Failure handling: hand platforms without a public API to manual verification.

## competitor-comparison-page-build

Time estimate: 3-6 hours.

1. Choose page type (vs, alternatives, roundup, comparison table) matched to query intent.
2. Build a verifiable feature matrix and dated pricing with sources; use "Not publicly available" rather than guessing.
3. Write balanced body copy (min ~1,500 words) with an honest verdict and disclosed own-product affiliation.
4. Generate Product/SoftwareApplication/ItemList schema; check the deprecation registry; add aggregateRating only when genuine ratings are visible.

Decision points: route legal-sensitive comparative claims to SEO Compliance & Legal Agent. Failure handling: if data is unverifiable, narrow to substantiated claims; set a quarterly review cadence.

## rendered-visual-audit

Time estimate: 30-90 minutes.

1. Detect a render capability (browser MCP, hosted screenshot MCP, or local Playwright). If none, degrade to raw-HTML and flag rendered checks skipped.
2. Render desktop and mobile viewports; capture full-page and above-the-fold screenshots.
3. Check above-the-fold value proposition and CTA visibility, mobile rendering, visual CLS risk, and rendered-vs-source delta (SPA risk).
4. Attach screenshots as evidence.

Decision points: no "visible above the fold" claim without a screenshot. Failure handling: raw-HTML analysis with an explicit skipped-checks banner.

## single-page-audit

Time estimate: 1-2 hours.

1. Fetch and classify the page; select the relevant skills by type.
2. Run baseline skills (technical, schema, content, CWV, rendered-visual, geo) plus type-specific skills, respecting cost gates.
3. Synthesize one consolidated page report with a single prioritized action list and no duplicate findings.

Decision points: recommend a full audit when the page implicates site-wide issues. Failure handling: run the subset that can execute and list skipped checks. See workflows/single-page-audit-workflow.md.

## flow-prompt-run

Time estimate: 1-3 hours.

1. Name the search surface and the business outcome before writing anything.
2. Decide the blocking stage: unclear demand language to Find; weak off-site corroboration to Leverage; hard-to-extract or low-trust asset to Optimize; traffic without business impact to Win; local visibility to Local.
3. Load only the matching file in `skills/flow-prompts/` and apply the relevant prompts. The stage files are references, not separate skills.
4. Separate observed evidence from assumption. Drop any statistic that has no supplied source.
5. Return the asset plus an evidence register (claim to source) and the measurement event that will judge it.

Decision points: route pricing, guarantee, and regulated claims to the SEO Compliance & Legal Agent. Failure handling: if the business outcome or evidence is missing, request it or write the safer version and mark the gaps; if the stage is unclear, run Find first.

## serp-overlap-cluster

Time estimate: 2-4 hours (needs supplied SERP results).

1. Expand the seed into 30-50 deduplicated variants.
2. Capture the top-10 organic URLs per keyword from a connected source or a supplied export. If none exists, stop and request it; never fabricate rankings, volumes, or intent.
3. Run `scripts/serp_cluster.py`: >= 4 shared top-10 URLs (or exactly 3) merges keywords; <= 2 keeps them separate. Output is deterministic for identical input.
4. Assign the hub (highest supplied volume, then connectivity) and spokes; build the internal-link matrix.
5. Deliver the cluster map and page plan. State that SERP overlap groups intent and does not prove ranking success.

Decision points: do not merge distinct-intent clusters on a few incidental shared URLs. Failure handling: with no SERP data, produce an intent-grouped draft labeled ANALYSIS and mark SERP validation pending.
