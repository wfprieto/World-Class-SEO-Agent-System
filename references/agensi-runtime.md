# Source and executable runtime

This is a small instruction wrapper, not an embedded Python application.
The unmodified public source is pinned to commit `44a95767e18b954b0060c4a913e262a5d19d7108`
of [wfprieto/World-Class-SEO-Agent-System](https://github.com/wfprieto/World-Class-SEO-Agent-System/tree/44a95767e18b954b0060c4a913e262a5d19d7108).
Bundled canonical references are unchanged copies from that commit. Preserve
the included MIT licence; packaging is not a marketplace or legal approval.

## Local source versus marketplace delivery

If a complete approved checkout is already available, inspect its Python version,
source identity and dependencies before using it. Do not reset, overwrite, or
replace a user's checkout. Report a different commit or local changes rather than
silently treating them as this package's verified baseline.

If no complete checkout is available, explain that executable mode needs one.
Only after the operator approves fetching and installing public upstream source,
use a new empty destination. These commands fetch from the public repository,
not from a marketplace-delivered skill:

```sh
git clone --no-checkout https://github.com/wfprieto/World-Class-SEO-Agent-System.git world-class-seo-runtime
git -C world-class-seo-runtime checkout --detach 44a95767e18b954b0060c4a913e262a5d19d7108
cd world-class-seo-runtime
git rev-parse HEAD
```

Never copy the paid skill or its references to make that checkout. Agensi delivers
scripts as individual temporary files; this multi-file application needs its
normal imports, resources, and directory layout. Without local execution or
approved source retrieval, provide advisory analysis only, with that limitation
clearly stated. Do not imply that documentation-only output equals executed CLI proof.

## Environment and offline checks

The source supports CPython 3.11, 3.12 and 3.13. Use an operator-approved isolated
Python environment. After approval for dependency installation, the documented
core install is `python -m pip install -e .`, run from the full checkout.
No virtual environment or installed dependency is included in this ZIP.
Optional browser rendering needs its separately approved browser dependencies;
do not install or download browsers for ordinary offline fixture use.

From that full checkout and environment, use:

```sh
python -m seoctl.entrypoint --registry-check
python -m seoctl.entrypoint system doctor
python -m seoctl.entrypoint audit technical --url https://example.com/ --fixture examples/product-proof/site-fixture.json --output outputs/first-run --max-urls 20
```

Choose a new output directory if `outputs/first-run` already contains user work.
The doctor and fixture audit perform no provider or live-site authentication.
If a check fails, retain the failure and its cause; do not disable the check or
present missing evidence as passing.

The expected ten outputs are `crawl.json`, `findings.json`, `decisions.json`,
`agent-contributions.json`, `trust-summary.json`, `technical-audit.md`,
`executive-summary.md`, `remediation-plan.csv`, `verification-plan.json`,
and `run-manifest.json`. The manifest must identify `FIXTURE` evidence mode.
Use the source command help for other options; do not guess CLI flags.

## External tools and paid data

This wrapper does not ship keys, enable paid tools, alter the system's adapters,
or define an Agensi-to-CLI connection. Agensi's actual tool names, availability,
billing approval and unit rates must be checked in the executing host before
any metered use. Preserve native receipts/provenance when normalizing data;
if no compatible authorized adapter exists, report the missing contract rather
than inventing a provider response. Do not send private client data to a provider
without the operator's approval.

Agensi's scanner, listing-name availability, remote skill loading, creator terms,
and paid-provider execution have not been tested by building this local ZIP.
