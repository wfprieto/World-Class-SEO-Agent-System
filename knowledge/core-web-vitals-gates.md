# Core Web Vitals Evaluation Gates

**Status:** Primary-source reconciled baseline  
**Version:** 2.0.0  
**Last reconciled:** 2026-07-10  
**Next scheduled review:** 2026-10-10, or when web.dev changes a Core Web Vital or its thresholds  
**Primary consumers:** SEO Technical Agent, single-page audit, and drift monitoring  
**Canonical source path:** `knowledge/core-web-vitals-gates.md`

## Purpose

This file defines evidence, thresholds, classifications, and failure states for `core-web-vitals-triage`, preventing lab scores, display strings, or one metric from being presented as a complete result.

## Governing facts

- The current Core Web Vitals are LCP, INP, and CLS; a page or origin passes only when **all three** meet the “good” threshold at the 75th percentile of field observations.
- Mobile and desktop must be evaluated separately.
- Field data describes experienced performance. Lab data helps diagnose causes. Do not substitute one for the other.
- Core Web Vitals are one part of page experience and do not guarantee ranking improvement.

## Field thresholds

| Metric | Good | Needs improvement | Poor | Unit |
|---|---:|---:|---:|---|
| LCP | `<= 2500` | `> 2500` and `<= 4000` | `> 4000` | milliseconds |
| INP | `<= 200` | `> 200` and `<= 500` | `> 500` | milliseconds |
| CLS | `<= 0.10` | `> 0.10` and `<= 0.25` | `> 0.25` | unitless |

Boundary values belong to the better band shown above. Store normalized numeric values, not localized strings such as “2.5 s”.

## Representativeness gate

Before classifying field data, confirm the source identifies the collection window, URL or origin scope, device class, and metric values. If the source withholds sample size or representativeness details, disclose that limitation rather than inventing a traffic threshold.

Decision algorithm:

1. Normalize LCP and INP to milliseconds and CLS to a numeric unitless value.
2. Evaluate the exact page and device class first.
3. If page-level data is unavailable, use origin data only as an explicitly labeled fallback.
4. Classify each available metric using the inclusive boundaries below.
5. Return `PASS` only when all three field metrics are present and good.
6. Return `FAIL` when all required field metrics are present and at least one is not good.
7. Return `PARTIAL`, `NO_FIELD_DATA`, `LAB_ONLY`, or `ERROR` for the named incomplete state.

## Assessment states

Return one of these states per device class and data level:

- `PASS`: LCP, INP, and CLS all have representative field data and all pass at p75.
- `FAIL`: all required field metrics are available and one or more fail.
- `PARTIAL`: field data exists but one or more required metrics are missing or not representative.
- `NO_FIELD_DATA`: CrUX or another approved field source has no usable data.
- `LAB_ONLY`: only controlled-test data is available. This is diagnostic, not a Core Web Vitals pass.
- `ERROR`: collection, parsing, integrity, or authorization failed.

Never convert `PARTIAL`, `NO_FIELD_DATA`, or `LAB_ONLY` into a passing score.

## Evidence hierarchy

1. Page-level field data for the exact URL and device class.
2. Origin-level field data, explicitly labeled as an origin fallback.
3. Approved first-party RUM, with sampling and collection method disclosed.
4. Lab measurements from Lighthouse, WebPageTest, or DevTools for diagnosis.
5. Static-code or visual risk observations as hypotheses only.

Record source, collection period, device/form factor, URL scope, sample limitations, and collection timestamp. CrUX values commonly represent a rolling 28-day collection period, so recent fixes may not immediately appear in field data.

## LCP diagnostic model

Use the four LCP subparts when available:

`LCP = TTFB + resource load delay + resource load duration + element render delay`

| Subpart | Diagnostic question | Common evidence |
|---|---|---|
| TTFB | Was the initial document response delayed? | Server timing, cache status, redirects, CDN/origin traces |
| Resource load delay | Did the browser discover and prioritize the LCP resource promptly? | Preload/priorities, parser discovery, CSS background usage |
| Resource load duration | Was the LCP resource slow to transfer? | Bytes, format, compression, network waterfall |
| Element render delay | Was the resource available but prevented from painting? | CSS/JS blocking, fonts, client rendering, visibility changes |

A TTFB of `<= 800 ms` may be used as a **rough diagnostic guide**, not as a Core Web Vitals pass/fail criterion.

## Metric-specific diagnostics

### LCP

Check the actual LCP element and evidence before recommending a fix. Common causes include response latency, redirects, render-blocking resources, late discovery, oversized media, client-side rendering, and delayed fonts. Do not assume the hero image is the LCP element.

### INP

Use field attribution or a reproducible interaction trace where possible. Check long tasks, event handlers, main-thread contention, rendering work, third-party scripts, DOM complexity, and layout work. Treat any fixed DOM-size number as a diagnostic clue, not a Google threshold.

### CLS

Inspect unexpected shifts during the page lifecycle, not only initial load. Common causes include media without reserved dimensions, injected UI, ads or embeds without reserved space, font changes, and animations that trigger layout.

## SPA and soft-navigation handling

Single-page applications require special disclosure:

- Traditional page-load field data can underrepresent route-level experiences created by soft navigations.
- Chrome's soft-navigation measurement APIs are in transition toward unflagged availability from Chrome 151, according to the Chrome team as of July 2026.
- Detect support before using the API, version the instrumentation, and preserve the URL/navigation identifier associated with each route transition.
- Do not claim that current Search ranking systems use custom soft-navigation RUM unless a current Google primary source confirms it.
- Until route-level evidence is representative, report both initial-load CWV and route-transition diagnostics separately.

## Evidence reuse, privacy, and escalation

Reuse one canonical PageSpeed/CrUX capture per URL, form factor, and run rather than issuing duplicate calls or copying inconsistent metrics into separate reports. Treat raw real-user monitoring data, URLs with sensitive query parameters, and client telemetry as controlled evidence. Escalate release-blocking regressions, missing representative field data, or conflicts between lab and field evidence to the Technical Owner before claiming remediation.

## Required output

For each URL or origin, return:

- Scope: page or origin
- Device class
- Collection period and timestamp
- LCP, INP, and CLS numeric p75 values
- Per-metric classification
- Overall assessment state
- Page/origin fallback disclosure
- Field-versus-lab comparison
- Evidence-backed bottleneck hypothesis
- Prioritized action with owner, acceptance criterion, and verification method

## Failure controls

- No field data: provide lab diagnostics and label `NO_FIELD_DATA` or `LAB_ONLY`.
- Conflicting sources: prefer the more specific, current, representative field source and disclose the conflict.
- Post-fix verification: use reproducible lab tests immediately and field data after a sufficient collection window.
- Tool or metric changes: mark affected claims `REVERIFY_AT_RUN` and update this file before client delivery.

## Primary sources

- Web Vitals overview: https://web.dev/articles/vitals
- LCP: https://web.dev/articles/lcp
- INP: https://web.dev/articles/inp
- CLS: https://web.dev/articles/cls
- Threshold methodology: https://web.dev/articles/defining-core-web-vitals-thresholds
- TTFB guidance: https://web.dev/articles/optimize-ttfb
- Soft-navigation measurement: https://developer.chrome.com/docs/web-platform/soft-navigations
