# FLOW Prompts - Leverage

## Use When

Use when the brand, author, product, service, location, or claim is not corroborated outside the
owned site. The Leverage stage builds legitimate authority signals that search engines, humans,
and AI answer systems can verify.

## Owner Agents

- Digital PR & Programmatic Link Outreach Agent
- Competitive Intelligence Agent
- SEO Knowledge Graph Sync Agent
- Negative SEO & Security Agent
- SEO Compliance & Legal Agent

## Required Inputs

- Brand, entity, product, author, or location being strengthened.
- Current backlink and mention evidence, if available.
- Competitor backlink, citation, review, or SERP evidence.
- Existing proprietary data, examples, media, research, tools, or proof assets.
- Compliance constraints for claims, outreach, endorsements, sponsorship, and privacy.

## Stop Conditions

- User asks for link buying, private blog networks, fake reviews, fake citations, or undisclosed
  sponsorships.
- Outreach target list lacks relevance or any legitimate value exchange.
- Claims require legal/compliance review and no reviewer is available.

## Decision Tree

1. If brand/entity facts are inconsistent, run `entity-corroboration-map`.
2. If competitors have stronger authority, run `competitor-authority-gap`.
3. If there are unlinked mentions, run `unlinked-mention-recovery`.
4. If the site has original data or expertise, run `linkable-asset-plan`.
5. If backlink risk is suspected, run `negative-seo-risk-screen`.
6. If backlink APIs or prospecting tools are requested, run `cost-aware-link-prospecting-plan`.
7. If outreach is requested, route through compliance before drafting.

## Prompt Blocks

## Prompt: Entity Corroboration Map

```text
Act as an authority and entity-corroboration strategist for [brand/entity] in [market].

Using supplied evidence only, map where the entity should be consistently represented:
- owned site
- Google Business Profile or equivalent local profile
- social profiles
- author/publisher pages
- industry directories
- review platforms
- knowledge graph profiles
- reputable press or community references
- partner/vendor/customer references

Return:
1. Current fact table: name, URL, sameAs profiles, address/service area, phone, authors, products.
2. Contradictions or missing corroboration.
3. Priority fixes by impact and effort.
4. Evidence needed to confirm each change.

Rules:
- Do not recommend fabricating profiles.
- Do not treat weak directories as authority unless they are relevant to the market.
```

## Prompt: Competitor Authority Gap

```text
Analyze supplied competitor backlink, citation, mention, and SERP evidence.

Return:
1. Competitor authority sources by type: editorial, directory, review, partnership, data citation,
   community, video, podcast, tool, documentation, or local citation.
2. Asset types earning links or mentions.
3. Realistic opportunities the brand could earn.
4. Opportunities that are not worth pursuing.
5. Required asset or proof before outreach.

Prioritize:
- relevance over raw domain metrics
- editorial legitimacy over volume
- earned corroboration over manipulative links
```

## Prompt: Unlinked Mention Recovery

```text
For the supplied unlinked brand/entity mentions, classify each opportunity:
- high value: relevant, recent, editorial, accurate, likely to update
- medium value: relevant but low authority or hard to update
- low value: weak, spammy, irrelevant, or risky

Return:
1. Target URL or source.
2. Mention context.
3. Suggested correction or link target.
4. Outreach angle.
5. Risk/compliance notes.

Rules:
- Do not request links where the citation would be misleading.
- Do not imply a relationship that does not exist.
```

## Prompt: Linkable Asset Plan

```text
Design linkable assets from real expertise or proprietary evidence.

Inputs:
- company data
- customer findings
- original research
- tools/calculators
- templates
- benchmark data
- expert commentary
- visual assets

Return:
1. Asset idea.
2. Why it deserves citations.
3. Target audience and publication types.
4. Evidence required.
5. Outreach angle.
6. Internal page that should receive authority.
7. Measurement plan.

Reject:
- generic listicles with no information gain
- copied statistics roundups
- assets requiring data the business does not have
```

## Prompt: Cost-Aware Link Prospecting Plan

```text
For [brand/site], decide whether link prospecting can be done from free evidence or needs a paid
backlink/mention API.

Inputs:
- target domain or page
- budget tier and credential availability
- existing backlink exports, GSC links, brand mentions, partner lists, press mentions, or competitor URLs
- outreach compliance constraints
- desired decision: risk review, opportunity discovery, authority gap, or campaign build

Return:
1. Free-first path: existing mentions, partner/customer/vendor pages, press, industry directories, and manual SERP checks.
2. Paid-data path: backlink, referring-domain, lost-link, or mention data needed.
3. Relevance filter: topical relevance, editorial legitimacy, geography, audience, and relationship context.
4. Risk filter: paid links, private networks, spam neighborhoods, irrelevant domains, or undisclosed sponsorship.
5. Cost and quota risk: Low / Medium / High.
6. Outreach permission state: allowed, needs legal review, blocked, or evidence missing.

Rules:
- Do not equate high domain metrics with a good opportunity.
- Do not recommend paid, undisclosed, fake, or manipulative link acquisition.
- If budget or credentials are missing, produce a free-first prospecting brief.
```

## Prompt: Negative SEO Risk Screen

```text
Review supplied backlink or mention evidence for defensive SEO risk.

Flag:
- sudden link velocity spikes
- irrelevant foreign-language spam
- exact-match anchor flooding
- scraped duplicate content
- hacked-page links
- malware or adult/gambling/pharma neighborhoods
- toxic redirect chains

Return:
1. Risk level.
2. Evidence refs.
3. Whether to monitor, investigate, contact source, or prepare disavow.
4. Why disavow is or is not justified.

Rules:
- Do not recommend disavow from weak evidence.
- Separate observed risk from suspicion.
```

## Output Contract

Return:

- Minimum JSON keys: `"stage"`, `"authority_gap"`, `"authority_actions"`,
  `"forbidden_actions_rejected"`, `"evidence_register"`, `"compliance_review"`,
  `"measurement"`.
- `"stage": "leverage"`
- `authority_gap`: entity, backlink, citation, or reputation gap
- `authority_actions`: prioritized ethical actions
- `tool_plan`: free-first or paid-data path with budget and compliance guardrails
- `forbidden_actions_rejected`: any manipulative tactics refused
- `evidence_register`: claim to source mapping
- `compliance_review`: required / not required, with reason
- `measurement`: links, mentions, citations, share of voice, rankings, or referral outcomes
