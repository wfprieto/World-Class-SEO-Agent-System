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

1. Use the repository's **Security** tab and select **Report a vulnerability**.
2. Include the affected version or commit, affected files or workflow, safe reproduction steps, impact, and any suggested remediation.
3. If that private-reporting option is temporarily unavailable, open a minimal public issue requesting private coordination. Do not include sensitive details.

The maintainer will acknowledge reports and coordinate remediation privately when possible.

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
