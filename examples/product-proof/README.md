# Product-Proof Examples

These files exercise deterministic contracts. They are not live-site or live-platform proof.

```bash
seoctl audit technical --url https://example.com/ --fixture examples/product-proof/site-fixture.json --output audit-runs/fixture --max-urls 20
seoctl intelligence ai-timeouts --log examples/product-proof/access.log --server-stack nginx
seoctl intelligence ai-citations --observations examples/product-proof/ai-observations.json
seoctl intelligence review-compliance --input examples/product-proof/review-practices.json
seoctl intelligence performance-narrative --input examples/product-proof/performance.json
seoctl knowledge product-claims --status BLOCKED
```
