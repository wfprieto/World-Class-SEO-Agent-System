# Multi-Agent Tracer

This deterministic tracer is the early falsification gate for the system's highest-risk assumption: adding specialist agents must improve evidence, conflict handling, and action quality rather than merely increase calls.

It uses three seeded cases:

1. content publication versus an accidental `noindex` technical dependency;
2. growth copy versus an unsupported comparative claim;
3. duplicate canonical findings from technical and e-commerce specialists.

Run:

```powershell
python evaluation/tracer/run_tracer.py
```

A `GO` verdict requires all seeded safety checks to pass and improvement in at least two measured dimensions. A `NO_GO` verdict blocks further capability expansion until agent roles, graph composition, evidence sharing, or synthesis are corrected.

The tracer is intentionally small and deterministic. It does not replace the later full benchmark corpus or independent human SEO review.
