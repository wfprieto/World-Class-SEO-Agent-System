# AI Search, Retrieval, and Extraction Asset

**Authority:** SEO BIBLE 2026 Parts 9 and 10.3.  
**Evidence rule:** Primary Google controls are factual. Platform observations and practitioner mechanisms remain dated observations or hypotheses unless independently verified.

## Distinct surfaces

Keep these separate:

- Search-index crawling
- Training crawlers
- User-triggered retrieval
- AI answer citations
- Google AI Overviews and AI Mode

Blocking a vendor training crawler does not necessarily block that vendor's user-triggered retrieval. AI crawler rules do not control Google's AI Overviews when those answers are grounded in the regular Google index.

## Google extraction controls

`nosnippet` suppresses normal snippets and direct content use in Google AI features. `max-snippet` limits both snippet length and potential direct input. `data-nosnippet` excludes selected page sections. These are visibility trade-offs and require business approval.

## Measurement layers

- Observed: dated citations, referrals, landing pages, conversions, revenue.
- Proxy: branded-search changes, surveys, direct traffic, social listening.
- Modeled: planning estimates only.

Never combine the three into one factual AI-impact number.

## Retrieval diagnostics

- Compare raw HTML with browser-rendered output.
- Confirm pricing, attributes, trust signals, and primary answers exist without client-side JavaScript.
- Segment server logs by verified user-agent families.
- Treat nginx-family 499 responses as client-closed-request evidence only after confirming server semantics.
- User-agent strings can be spoofed; IP verification is a separate control.

## Citation opportunity

A high-value observed opportunity is a query where the site ranks in the top ten, an AI Overview is observed, and the site is not cited. Record platform, date, prompt, location/device context, competitors cited, citation order, destination URL, recommendation state, and narrative accuracy.
