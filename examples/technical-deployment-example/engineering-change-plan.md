# SEO Engineering Change Plan: sitemap canonical cleanup

Lead agent: Senior SEO Engineer Agent

## Scope

Update sitemap generation so only canonical, indexable, 200-status URLs are emitted.

## Files or Templates Affected

- `app/sitemap.ts`
- `lib/seo/url-policy.ts`

## Implementation Plan

1. Add URL eligibility helper.
2. Filter redirected, noindex, and non-canonical URLs.
3. Add regression tests for excluded URL states.

## Tests

- Sitemap unit test excludes redirected URLs.
- Sitemap unit test excludes noindex URLs.
- Sitemap unit test includes canonical published URLs.

## SEO Verification

Sample generated sitemap and confirm all URLs return 200 and self-canonicalize.

## Accessibility Verification

Not applicable; no rendered UI change.

## Rollback

Revert sitemap helper and redeploy previous sitemap generation.

