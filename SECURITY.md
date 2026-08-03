# Security Policy

## Supported versions

| Version or channel | Security support |
|---|---|
| Current `main` (`1.7.x` pre-release development) | Supported for coordinated fixes |
| Tagged releases | None published yet |
| Older commits and unmerged branches | Not supported |

`main` is the current development source of truth, but it is not described as a
published release. When the first versioned release is published, this table must
name the supported tag series and retirement policy. Supported runtime versions are
CPython 3.11, 3.12, and 3.13 on Windows and Ubuntu; Python 3.14+ is not certified.

## Report a vulnerability privately

Do **not** disclose vulnerabilities, exploit details, credentials, client data, private URLs, or proof-of-concept code in a public issue.

1. Open the repository's [private vulnerability report form](https://github.com/wfprieto/World-Class-SEO-Agent-System/security/advisories/new).
2. Include the affected version or commit, affected files or workflow, safe reproduction steps, impact, and any suggested remediation.
3. If that private-reporting option is temporarily unavailable, open a minimal public issue requesting private coordination. Do not include sensitive details.

The maintainer will acknowledge reports and coordinate remediation privately.

## System boundary and threat model

The protected system includes the Python runtime and CLI, provider adapters, integration
transports, schemas, workflows, release tooling, generated evidence, and repository automation.
The following inputs are untrusted even when they come from an authenticated user or provider:

- URLs, redirects, DNS answers, fetched page content, robots files, sitemaps, and browser output
- API responses, webhook-like payloads, model output, fixtures, and imported JSON
- command-line arguments, environment variables, configuration, and contributed repository changes
- filenames, archive contents, report content, and provenance or evaluation records

Important trust boundaries are the local process to network boundary, adapters to third-party
providers, model output to deterministic execution, repository content to GitHub Actions, and
generated evidence to a human approval decision. Attackers may attempt SSRF, redirect or DNS
rebinding, prompt or content injection, schema confusion, path traversal, secret disclosure,
workflow supply-chain compromise, evidence forgery, denial of service, or unsafe SEO mutations.

## Security invariants

- Network destinations must pass the repository's URL-safety policy before each request and after
  redirects; private, loopback, link-local, and otherwise prohibited destinations remain blocked.
- Credentials and private client data must not enter logs, fixtures, issues, generated reports, or
  committed artifacts.
- Provider and model output is data, not executable authority. Deterministic validation and explicit
  approval gates remain authoritative.
- Schema, provenance, and remediation evidence must fail closed when required fields, hashes,
  identities, or provider observations are missing or inconsistent.
- Material changes must pass `repository-certification` and receive an approval from someone other
  than the last pusher before they enter `main`.
- Workflows use least-privilege permissions; release authority is separate and is not granted to
  ordinary pull-request validation.

## Reportability and severity

Please report any credible violation of an invariant, bypass of a safety control, unauthorized data
access, integrity loss, or supply-chain compromise. Severity is assessed from demonstrated impact,
reachability, required privileges, affected data or systems, and whether exploitation crosses a
documented trust boundary. SEO-only correctness defects without a security impact belong in a bug
report; issues capable of exposing secrets, reaching internal services, executing untrusted code,
or silently corrupting authoritative evidence should be treated as security reports.

## Limitations and compensating controls

This repository does not make third-party providers, arbitrary websites, model output, or user
environments trustworthy. It cannot guarantee that a permitted external site is benign or that a
provider remains available. Network allow/deny checks, bounded retries and payloads, schema
validation, explicit provenance, CI certification, protected-branch review, and non-production
fixtures reduce those risks. Operators remain responsible for authorization, credential scoping,
client-data handling, provider terms, and reviewing recommendations before applying them.

## Security scope

Reports are welcome for vulnerabilities in repository code, workflows, dependencies, release artifacts, and example integrations. SEO-operational risks in scope include:

- Hacked-page or malware exposure
- Index pollution or spam injection
- Unsafe crawling or SSRF paths
- Credential or sensitive-data exposure
- Robots, canonical, redirect, or sitemap changes that could cause material visibility harm

## Out of scope

Normal documentation issues, feature requests, SEO recommendations, and third-party service outages should be reported through the relevant public issue form.

## Safe disclosure expectations

Please give maintainers a reasonable opportunity to investigate and release a fix before public disclosure. Do not access data you are not authorized to access, disrupt services, or use a vulnerability beyond what is necessary to demonstrate impact.
