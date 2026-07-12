# Authority, Media, Provenance, and Drift Pack

Verified: 2026-07-11

This pack adds bounded operator commands for public crawl-index evidence, supplied backlink exports, public RDAP registration data, YouTube search, IPTC Digital Source Type sidecars, transcript structure, and page-state drift. It does not create a second evidence database, background daemon, autonomous outreach workflow, or binary media writer.

## Commands

```text
seoctl links commoncrawl
seoctl links profile
seoctl links gap
seoctl domain history
seoctl media youtube-search
seoctl media iptc-label
seoctl media transcript-check
seoctl drift baseline
seoctl drift compare
seoctl drift history
seoctl drift report
seoctl drift watch
```

## Evidence boundaries

### Common Crawl

`links commoncrawl` queries a bounded sample of the Common Crawl CDX URL index. It records crawl-index presence and archive metadata. It does not claim complete crawl coverage, link existence today, incoming-link direction, link quality, or a complete backlink graph. Bulk WARC or columnar-index analysis remains outside this command.

Official sources:

- https://index.commoncrawl.org/
- https://commoncrawl.org/get-started

The official index page identifies the CDX URL index, publishes archive endpoints, states that the data and index files are free to download, warns against overloading the public index, and directs bulk analysis to the downloadable or columnar indexes.

### Backlink profile and gap

`links profile` and `links gap` normalize operator-supplied CSV or JSON records. They do not independently verify that a link remains live, that it passes ranking value, or that outreach is appropriate. No invented authority or quality score is emitted.

### Domain history

`domain history` uses the IANA RDAP bootstrap to locate the authoritative HTTPS RDAP service for the domain's top-level domain. The normalized output keeps public registration events, statuses, nameservers, secure-DNS evidence, registrar identifiers, notices, and RDAP conformance. Contact-card data is intentionally excluded.

Official sources:

- https://data.iana.org/rdap/dns.json
- https://www.rfc-editor.org/rfc/rfc9224
- https://www.rfc-editor.org/rfc/rfc9082
- https://www.rfc-editor.org/rfc/rfc9083

RDAP output may be redacted, incomplete, delayed, or inconsistent. Registration data does not establish beneficial ownership, site reputation, or historical content quality.

### YouTube

`media youtube-search` uses the current YouTube Data API `search.list` contract. API keys are read from `YOUTUBE_API_KEY` and sent in the `X-Goog-Api-Key` header. The generated request URL never contains the key. Result pagination is bounded to three pages and 50 results per page.

Official sources:

- https://developers.google.com/youtube/v3/docs/search/list
- https://developers.google.com/youtube/v3/determine_quota_cost

The official reference states that `maxResults` is bounded from 0 to 50, pagination uses page tokens, and `pageInfo.totalResults` is approximate. Current quota documentation, last updated June 1, 2026, assigns `search.list` a separate default bucket of 100 calls per day and a cost of one quota unit per request. Every additional page is another request.

Missing credentials return `NOT_CONFIGURED`. Fixture success is not live-provider proof.

### IPTC Digital Source Type

`media iptc-label` validates current IPTC Digital Source Type values in JSON metadata. It can write a new JSON sidecar only when all of these are present:

```text
--write
--authorize-write
--label <current IPTC term>
--output <new sidecar path>
```

The source file is never modified. Rollback is deletion of the generated sidecar. The command rejects retired `softwareImage` and `digitalArt` values and does not claim to edit EXIF, XMP, or embedded binary metadata.

Official source:

- https://cv.iptc.org/newscodes/digitalsourcetype/

The current vocabulary distinguishes captured, human-edited, algorithmically enhanced, human digital creation, trained-algorithmic media, generative-AI edits, pure algorithmic media, screen captures, virtual recordings, and composite types.

### Transcript checks

`media transcript-check` performs deterministic structural checks on supplied text, SRT, or WebVTT content. It reports timestamps, word and caption-line counts, repeated segments, long lines, and placeholder markers. It does not verify spoken-word accuracy, speaker identity, semantic completeness, copyright, or legal accessibility compliance.

### Drift

All drift commands reuse `adapters/evidence_store.py` through `adapters/page_drift.py`.

- `baseline` records a page-state snapshot.
- `compare` compares the two latest compatible verified snapshots.
- `history` returns verified snapshots.
- `report` optionally writes the current comparison as JSON.
- `watch` performs one bounded capture-and-compare operation.

`watch` does not create a scheduler or background process. Missing history remains `PARTIAL`/`insufficient_history`; it is never converted to "no drift." Tampered evidence fails closed before a verdict.

## Security and operational controls

- HTTPS only.
- Exact approved hosts for Common Crawl, IANA, and YouTube.
- RDAP's authoritative host must originate in the IANA bootstrap and is then exact-host allowlisted.
- No credentials in URLs, output, warnings, or exceptions.
- Bounded retries, timeouts, response sizes, pages, rows, and input files.
- No arbitrary redirects.
- No provider writes.
- IPTC output is a separately authorized sidecar, never an in-place mutation.
- Drift writes only to the canonical local EvidenceStore.

## Live state

The implementation and fixture contracts are testable without credentials. This phase does not claim live Common Crawl, RDAP, or YouTube smoke success unless a CI or operator run records the actual request evidence. Without that proof, live parity remains open.
