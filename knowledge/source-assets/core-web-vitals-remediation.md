# Core Web Vitals Remediation Asset

**Authority:** SEO BIBLE 2026 Part 12, derived from current Chrome/web.dev guidance.  
**Evidence rule:** Field data at the 75th percentile outranks lab data for user-experience conclusions. Lab evidence is diagnostic, not proof of field performance.

## Current thresholds

- LCP: 2.5 seconds or less
- INP: 200 milliseconds or less
- CLS: 0.1 or less

FID is deprecated and must not be taught as a current Core Web Vital.

## LCP diagnosis

Decompose LCP into TTFB, resource-load delay, resource-load duration, and element-render delay. Investigate delay before optimizing bytes.

High-priority checks:

1. The LCP resource is discoverable in initial HTML.
2. The LCP image is not lazy-loaded.
3. A CSS-background or JavaScript-injected LCP asset is preloaded when appropriate.
4. Only one or two likely LCP images use high fetch priority.
5. Synchronous head scripts, page-hiding experiments, and render-blocking CSS do not delay paint.
6. Tracking redirects and unique analytics parameters do not prevent edge caching or add TTFB.

## INP diagnosis

Separate input delay, processing duration, and presentation delay. Identify long tasks, script evaluation during load, layout thrashing, oversized DOMs, expensive iframes, and callbacks that perform nonvisual work before the next frame.

## CLS diagnosis

Check dimensions and reserved space for images, advertising, embeds, injected UI, and fonts.

## Prohibited conclusions

- Do not claim a passing Lighthouse run proves field performance.
- Do not optimize FID as a current Core Web Vital.
- Do not promise rankings from CWV work.
- Do not assume image compression improves LCP when render delay is the bottleneck.
