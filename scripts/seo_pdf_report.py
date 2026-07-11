"""Branded A4 report from the canonical agent-output shape.

Consumes `schemas/agent-output.schema.json` (agent, summary, evidence, confidence,
findings, recommended_actions, impact, effort, risks, owner, dependencies,
acceptance_criteria, verification, follow_up). It defines no second report contract and
performs no authentication, provider call, or provider-data normalization.

Optional dependencies (neither is required; the credential-free path always works):
- weasyprint  -> real PDF. Absent: a styled .html fallback is written instead.
- matplotlib  -> score chart. Absent: the chart is omitted.

The PDF renderer is injectable (`pdf_renderer`) so the PDF-success branch is testable
without a native runtime. The returned ReportResult states truthfully which artifact was
produced. A PDF pass is never claimed when only the HTML fallback ran.

Generated artifacts default to `outputs/` (git-ignored) so reports never enter source control.

Usage: python seo_pdf_report.py agent-output.json --out outputs/report.pdf
"""

from __future__ import annotations

import argparse
import base64
import html
import io
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

SEVERITY_COLOR = {
    "Critical": "#b00020", "High": "#d9534f", "Medium": "#e0a800", "Low": "#5a6b7b",
}
_REQUIRED = ("agent", "summary", "findings")
_MAX_HEADING = 300  # clamp pathological headings/URLs; escaping alone keeps them safe
DEFAULT_OUT = "outputs/seo-report.pdf"

DEPENDENCY_MISSING = "dependency_missing"
RENDER_FAILED = "render_failed"


@dataclass
class ReportResult:
    """Truthful record of what was actually produced."""
    format: str          # "pdf" | "html"
    path: Path
    message: str
    reason: str | None = None   # dependency_missing | render_failed (when format == "html")

    @property
    def pdf_verified(self) -> bool:
        return self.format == "pdf"

    def __str__(self) -> str:  # keeps CLI/back-compat string behaviour
        return self.message


def load_json(path: str) -> Any:
    """Read JSON tolerating a UTF-8 BOM."""
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def _clamp(text: str) -> str:
    text = str(text)
    return text if len(text) <= _MAX_HEADING else text[: _MAX_HEADING - 1] + "…"


def _score_chart(scores: dict[str, float], brand: str) -> str:
    if not scores:
        return ""
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except Exception:  # noqa: BLE001
        return ""
    try:
        names = list(scores)
        values = [float(scores[n]) for n in names]
    except (TypeError, ValueError):
        return ""  # missing or invalid chart data must not break the report
    figure, axis = plt.subplots(figsize=(5, 2.2))
    colors = ["#2e7d32" if v >= 90 else "#e0a800" if v >= 50 else "#b00020" for v in values]
    axis.barh(names, values, color=colors)
    axis.set_xlim(0, 100)
    axis.invert_yaxis()
    axis.set_xlabel("Score / 100")
    axis.spines[["top", "right"]].set_visible(False)
    buffer = io.BytesIO()
    figure.savefig(buffer, format="png", dpi=140, bbox_inches="tight", transparent=True)
    plt.close(figure)
    buffer.seek(0)
    return "data:image/png;base64," + base64.b64encode(buffer.read()).decode()


def _listing(title: str, items: list[Any]) -> str:
    if not items:
        return ""
    rows = "".join(f"<li>{html.escape(_clamp(i))}</li>" for i in items)
    return f"<h2>{html.escape(title)}</h2><ul>{rows}</ul>"


def build_html(data: dict, brand: str = "#0b5fff") -> str:
    if not isinstance(data, dict):
        raise TypeError("agent output must be a dict")
    missing = [k for k in _REQUIRED if k not in data]
    if missing:
        raise ValueError(f"agent output missing required fields: {', '.join(missing)}")

    findings = data.get("findings")
    if findings is not None and not isinstance(findings, list):
        raise ValueError("findings must be a list")

    chart = _score_chart(data.get("scores") or {}, brand)
    blocks = []
    for finding in findings or []:
        if isinstance(finding, dict):
            severity = str(finding.get("severity", "Medium"))
            title = str(finding.get("title", ""))
            detail = str(finding.get("detail", finding.get("evidence", "")))
        else:
            severity, title, detail = "Medium", str(finding), ""
        blocks.append(
            f'<div class="finding">'
            f'<span class="sev" style="background:{SEVERITY_COLOR.get(severity, "#5a6b7b")}">'
            f"{html.escape(_clamp(severity))}</span>"
            f"<h3>{html.escape(_clamp(title))}</h3><p>{html.escape(_clamp(detail))}</p></div>"
        )

    actions = [
        a.get("action", "") if isinstance(a, dict) else a
        for a in (data.get("recommended_actions") or [])
    ]
    meta = " · ".join(
        filter(None, [
            html.escape(_clamp(data.get("agent", ""))),
            "Confidence: " + html.escape(_clamp(data.get("confidence", "Unknown"))),
            "Owner: " + html.escape(_clamp(data.get("owner", "—"))),
        ])
    )
    body = "".join(blocks) or "<p>No findings recorded.</p>"
    return f"""<!doctype html><html><head><meta charset="utf-8"><style>
@page {{ size: A4; margin: 18mm 16mm; @bottom-center {{ content: "Confidential · " counter(page); font-size:8pt; color:#889; }} }}
body {{ font-family: -apple-system, Segoe UI, Roboto, Arial, sans-serif; color:#1b2733; font-size:10.5pt; }}
.band {{ border-left:6px solid {brand}; padding:2px 0 2px 12px; }}
h1 {{ font-size:19pt; margin:0; }} .meta {{ color:#5a6b7b; font-size:9pt; }}
h2 {{ font-size:13pt; margin:16px 0 6px; border-bottom:1px solid #e6ebf0; padding-bottom:3px; }}
h3 {{ font-size:11pt; margin:4px 0; word-break:break-word; }} img {{ max-width:100%; }}
.finding {{ border:1px solid #e6ebf0; border-radius:6px; padding:10px 12px; margin:8px 0; }}
.sev {{ display:inline-block; color:#fff; font-size:8pt; padding:1px 8px; border-radius:10px; }}
</style></head><body>
<div class="band"><h1>SEO Report</h1><div class="meta">{meta}</div></div>
<h2>Summary</h2><p>{html.escape(_clamp(data.get("summary", "")))}</p>
{'<h2>Scores</h2><img src="' + chart + '"/>' if chart else ''}
<h2>Findings</h2>{body}
{_listing("Recommended actions", actions)}
{_listing("Acceptance criteria", data.get("acceptance_criteria") or [])}
{_listing("Risks", data.get("risks") or [])}
<h2>Verification</h2><p>{html.escape(_clamp(data.get("verification", "Not recorded")))}</p>
</body></html>"""


def _weasyprint_renderer(markup: str, out: Path) -> None:
    from weasyprint import HTML  # imported lazily; optional dependency
    HTML(string=markup).write_pdf(str(out))


def dependency_status() -> dict[str, str]:
    """Optional-dependency availability, without rendering anything."""
    status = {}
    for module in ("weasyprint", "matplotlib"):
        try:
            __import__(module)
            status[module] = "installed"
        except Exception:  # noqa: BLE001
            status[module] = "missing"
    return status


def write_report(
    data: dict,
    out_path: str = DEFAULT_OUT,
    brand: str = "#0b5fff",
    pdf_renderer: Callable[[str, Path], None] | None = None,
) -> ReportResult:
    """Write a PDF when a renderer is available, else a styled HTML fallback.

    `pdf_renderer` is injectable so the PDF-success branch is testable without WeasyPrint.
    """
    if not isinstance(data, dict):
        raise TypeError("agent output must be a dict; use load_json() for a file path")
    markup = build_html(data, brand=brand)

    out = Path(out_path)
    try:
        out.parent.mkdir(parents=True, exist_ok=True)
    except (OSError, ValueError) as exc:
        raise ValueError(f"output location is not writable: {out.parent} ({exc})") from exc

    renderer = pdf_renderer
    reason: str | None = None
    if renderer is None:
        try:
            import weasyprint  # noqa: F401
            renderer = _weasyprint_renderer
        except Exception:  # noqa: BLE001
            reason = DEPENDENCY_MISSING

    if renderer is not None:
        try:
            renderer(markup, out)
            if not out.exists():
                raise RuntimeError("renderer reported success but produced no file")
            return ReportResult("pdf", out, f"PDF written: {out}")
        except Exception as exc:  # noqa: BLE001
            reason = RENDER_FAILED
            detail = str(exc)
    else:
        detail = "WeasyPrint is not installed"

    fallback = out.with_suffix(".html")
    try:
        fallback.write_text(markup, encoding="utf-8")
    except (OSError, ValueError) as exc:
        raise ValueError(f"output location is not writable: {fallback} ({exc})") from exc
    return ReportResult(
        "html",
        fallback,
        f"{reason}: {detail}. Wrote styled HTML fallback: {fallback}. PDF output is Not Run.",
        reason=reason,
    )


if __name__ == "__main__":  # pragma: no cover
    parser = argparse.ArgumentParser(description="Render an agent-output JSON as a report")
    parser.add_argument("agent_output")
    parser.add_argument("--out", default=DEFAULT_OUT)
    parser.add_argument("--brand", default="#0b5fff")
    args = parser.parse_args()
    print(write_report(load_json(args.agent_output), args.out, args.brand))
