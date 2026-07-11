# DMA and Consent Mode v2 (technical reference)

Technical reference for the `consent-mode-diagnostic` skill. **This is not legal advice.** Technical configuration does not establish legal compliance. Consent validity and DMA/GDPR obligations require qualified counsel.

**Evidence labels:** `FACT` confirmed against a Google-owned primary source. `ANALYSIS` reasoned. `VERIFY` time-sensitive, re-check before client use.
**Primary sources checked:** 2026-07-11.

## The four signals (`FACT`)

Consent Mode v2 requires all four:

| Signal | Governs |
|---|---|
| `ad_storage` | Advertising cookies and local storage |
| `analytics_storage` | Analytics cookies and local storage |
| `ad_user_data` | Whether user data may be **sent to Google** for advertising measurement |
| `ad_personalization` | Whether that data may be used for **personalised advertising and remarketing** |

`ad_user_data` and `ad_personalization` were added by v2. Omitting either is a critical defect.

## Ordering (`FACT`)

- The `default` command must run **before** any Google tag or GTM container loads and reads consent. "A tag read consent state before a default was set" means the ordering is broken.
- `default` runs once per page load. `update` reflects the user's choice and may fire **many** times, including granted → denied.
- `update` must be captured on the page where the choice occurs, before any navigation.
- `wait_for_update` (milliseconds) holds tags briefly for an incoming update. It is a **one-time window per page load, not a rolling timer**.

## Region defaults (`FACT`)

Defaults can vary by region. Where a region and a subregion both set a value, **the more specific region wins** — for example `US-CA` denied overrides `US` granted for a California visitor.

In consent-required regions (EEA, UK, CH), default all four signals to **denied** and change state only from the user's own choice. **Never grant consent on the user's behalf, and never bypass or manipulate the CMP.**

## Basic vs Advanced (`FACT`)

- **Advanced:** Google tags load *before* the banner and send cookieless pings without identifiers until consent is granted. More signal, more surface area.
- **Basic:** tags are blocked until the user consents. Nothing is sent pre-consent, so non-consented behaviour depends on **modeled** measurement.

## Unknown and stale states (`ANALYSIS`, safety rule)

Missing, unknown, or stale consent states must be treated as **denied**, never as granted. Absence of a denial is not consent.

## Modeled measurement (`FACT`)

Modeled conversions and behavioural modelling are Google **estimates**, not observed user data. Never report modeled figures as measured.

## Common defects

Update before default · missing `ad_user_data` or `ad_personalization` · granted-by-default in the EEA · duplicate container initialisation racing consent state · SPA route changes losing consent state · Preview configuration passing while Production differs · cross-domain consent not propagated · server-side tagging forwarding data that was never consented.

## Evidence and debugging

Use Google Tag Assistant's consent debugging to observe the resolved consent state and command order. Record the environment (Production vs Preview) with every finding: **Preview evidence is not proof of Production behaviour.**

Never record consent strings, TC strings, user identifiers, or any personal data in an audit artifact.

## Guardrails

Do not grant consent automatically. Do not bypass a CMP. Do not change live tags or consent settings without explicit authorisation. Do not run production tests that create advertising or analytics writes without approval. Do not claim technical implementation equals legal compliance. Flag legal interpretation for qualified counsel.

## Primary sources

- Set up consent mode on websites: https://developers.google.com/tag-platform/security/guides/consent
- Troubleshoot consent mode with Tag Assistant: https://developers.google.com/tag-platform/security/guides/consent-debugging
- Google Ads consent mode reference: https://support.google.com/google-ads/answer/13802165
- European Commission, Digital Markets Act: https://digital-markets-act.ec.europa.eu/

Re-verify these pages before client-facing use; consent behaviour and regional requirements change.
