# AI-Generated and AI-Edited Media Provenance

**Status:** Primary-source reconciled baseline  
**Version:** 2.0.0  
**Last reconciled:** 2026-07-10  
**Next scheduled review:** 2026-10-10, or immediately after Merchant Center, IPTC, or C2PA policy changes  
**Primary consumers:** SEO E-commerce Agent, image audit workflows, and SEO Compliance & Legal Agent

## Purpose and scope

This file separates mandatory platform requirements from kit controls for AI-generated or AI-edited media used in SEO, editorial content, product feeds, and Merchant Center. Provenance records declared origin and editing; it does not prove accuracy, legality, product fidelity, or absence of manipulation.

## Evidence labels

- `REQUIRED`: explicitly required by a current platform policy for the stated use.
- `STANDARD`: defined by IPTC or C2PA.
- `KIT_POLICY`: an internal transparency or risk-control requirement.
- `REVERIFY_AT_RUN`: a platform or standards detail that must be rechecked before delivery.

## Google Merchant Center requirements

As of this reconciliation:

- All images created using generative AI and submitted in Merchant Center image attributes must preserve metadata identifying the AI-generated source using IPTC `DigitalSourceType` with `TrainedAlgorithmicMedia`.
- Google also instructs merchants not to remove embedded digital-source metadata and lists relevant IPTC source codes such as `TrainedAlgorithmicMedia`, `CompositeSynthetic`, and `AlgorithmicMedia`.
- AI-generated product titles must use the structured title `[structured_title]` attribute with `digital_source_type=trained_algorithmic_media`.
- AI-generated product descriptions must use the structured description `[structured_description]` attribute with `digital_source_type=trained_algorithmic_media`.

These are product-data requirements, not evidence of a Google Search ranking benefit.

## IPTC Digital Source Type mapping

| Media condition | IPTC value | Use |
|---|---|---|
| Fully generated with a trained generative model | `trainedAlgorithmicMedia` | `STANDARD`; required by current Merchant Center policy for generative-AI product images |
| Human-origin image edited with generative AI, such as inpainting or outpainting | `compositeWithTrainedAlgorithmicMedia` | `STANDARD`; use when it accurately describes the editing history |
| Purely algorithmic media not based on sampled training data | `algorithmicMedia` | `STANDARD`; use only when technically accurate |

Do not label every automated transformation as generative AI. Conventional resizing, compression, color correction, or non-generative editing should use the source classification that accurately reflects the asset's history.

### Code compatibility caution

Google Merchant Center's current help page and the broader IPTC vocabulary do not use identical labels for every composite case. Do not assume `CompositeSynthetic` and `compositeWithTrainedAlgorithmicMedia` are interchangeable in a feed or downstream validator. For Merchant Center delivery, follow the current Google-supported values; for asset provenance, record the precise IPTC term that accurately describes the edit history. When both systems are involved, validate the final asset and feed separately.

## C2PA / Content Credentials

C2PA is an opt-in framework for signed provenance manifests and Content Credentials. Use it when tamper-evident history, issuer identity, or chain of custody matters. It complements IPTC but does not prove depicted claims or guarantee downstream preservation or display.

## Visible-disclosure gate

Use visible disclosure, not metadata alone, when a reasonable viewer could be materially misled about:

- whether a depicted product, person, event, property, medical result, or before/after outcome is real
- whether an image accurately represents what a buyer will receive
- whether documentary or news imagery records an actual event
- whether a regulated, YMYL, testimonial, or performance claim is substantiated

Do not present a synthetic representation as a photograph of the actual product or result when material differences exist.

## Required workflow

1. Load the current Merchant Center policy, the approved asset-pipeline specification, and the canonical asset record; if any dependency is unavailable, mark the affected decision `REVERIFY_AT_RUN`.
2. Classify the asset: captured, conventional edit, generative edit, fully generated, composite, or unknown.
3. Record creator/tool, generation or edit date, source assets, rights/consent status, and intended use.
4. Apply the accurate IPTC Digital Source Type.
5. Add C2PA credentials when required by policy or risk level and supported by the workflow.
6. Verify that export, DAM, CDN, optimization, and feed pipelines preserve required metadata.
7. Confirm visible disclosure when the risk gate applies.
8. Validate the final delivered asset, not only the source file.
9. Retain one canonical provenance record per final asset and reference it from downstream reports rather than creating conflicting copies. Do not expose private prompts, personal data, credentials, or licensed source assets unless an approved purpose requires them.
10. For high-risk, testimonial, regulated, documentary, or materially altered product media, require an independent reviewer to challenge the classification, disclosure, and fidelity decision before approval.

## Required validation evidence

For every approved high-risk or Merchant Center asset, retain:

- final asset hash or immutable identifier
- declared source classification and exact metadata value
- metadata inspection result after the final CDN/feed transformation
- visible-disclosure decision and reviewer
- product-fidelity or factual-accuracy review result
- validation date, tool/method, and exceptions

A source-file pass is insufficient when the delivered asset differs.

## Audit states

- `PASS`: required metadata is accurate and survives the final delivery path; visible disclosure is sufficient where needed.
- `PARTIAL`: source labeling exists, but downstream preservation or disclosure is not fully verified.
- `FAIL`: required metadata is absent/incorrect, the pipeline strips it, or the presentation is materially misleading.
- `UNKNOWN`: origin or edit history cannot be established.

Unknown provenance for a high-risk or Merchant Center asset blocks approval until resolved.

## Alt text and filenames

Write alt text for the image's user-facing purpose and content, not as a provenance field or keyword container. Provenance belongs in the applicable metadata and disclosure system. Filenames should be useful and non-deceptive, but filenames do not satisfy Merchant Center provenance requirements.

## Primary sources

- Google Merchant Center AI-generated content policy: https://support.google.com/merchants/answer/14743464
- IPTC Digital Source Type vocabulary: https://cv.iptc.org/newscodes/digitalsourcetype/
- IPTC generative-edit value: https://cv.iptc.org/newscodes/digitalsourcetype/compositeWithTrainedAlgorithmicMedia
- C2PA specification: https://spec.c2pa.org/specifications/specifications/2.4/specs/C2PA_Specification.html
