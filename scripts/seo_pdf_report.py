"""Render canonical SEO agent output as a branded PDF or truthful HTML fallback.

The renderer preserves finding text, scope, evidence references, actions, owners,
acceptance criteria, verification, risks, impact, and follow-up. Legacy title/detail
fixtures remain readable without becoming a second report contract.
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
    "Critical": "#b00020",
    "High": "#d9534f",
    "Medium": "#e0a800",
    "Low": "#5a6b7b",
}
_REQUIRED = ("agent", "summary", "findings")
_MAX_HEADING = 600
_MAX_BODY = 4000
DEFAULT_OUT = "outputs/seo-report.pdf"
DEPENDENCY_MISSING = "dependency_missing"
RENDER_FAILED = "render_failed"


@dataclass
class ReportResult:
    format: str
    path: Path
    message: str
    reason: str | None = None

    @property
    def pdf_verified(self) -> bool:
        return self.format == "pdf"

    def __str__(self) -> str:
        return self.message


def load_json(path: str) -> Any:
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def _clamp(value: Any, maximum: int = _MAX_HEADING) -> str:
    text = str(value)
    return text if len(text) <= maximum else text[: maximum - 1] + "…"


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
        values = [float(scores[name]) for name in names]
    except (TypeError, ValueError):
        return ""
    figure, axis = plt.subplots(figsize=(5, 2.2))
    colors = ["#2e7d32" if value >= 90 else "#e0a800" if value >= 50 else "#b00020" for value in values]
    axis.barh(names, values, color=colors)
    axis.set_xlim(0, 100)
    axis.invert_yaxis()
    axis.set_xlabel("Score / 100")
    axis.spines[["top", "right"]].set_visible(False)
    buffer = io.BytesIO()
    figure.savefig(buffer, format="png", dpi=140, bbox_inches="tight", transparent=True)
    plt.close(figure)
    return "data:image/png;base64," + base64.b64encode(buffer.getvalue()).decode()


def _listing(title: str, items: list[Any]) -> str:
    if not items:
        return ""
    rows = "".join(f"<li>{html.escape(_clamp(item, _MAX_BODY))}</li>" for item in items)
    return f"<h2>{html.escape(title)}</h2><ul>{rows}</ul>"


def _as_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item) for item in value]
    if value in (None, ""):
        return []
    return [str(value)]


def _evidence_block(items: list[Any]) -> str:
    rows: list[str] = []
    for item in items:
        if not isinstance(item, dict):
            rows.append(f"<li>{html.escape(_clamp(item, _MAX_BODY))}</li>")
            continue
        label = item.get("id") or item.get("source") or "Evidence"
        details = " · ".join(
            part
            for part in (
                str(item.get("type", "")),
                str(item.get("date_checked", "")),
                str(item.get("notes", item.get("detail", ""))),
            )
            if part
        )
        suffix = f": {html.escape(_clamp(details, _MAX_BODY))}" if details else ""
        rows.append(f"<li><strong>{html.escape(_clamp(label))}</strong>{suffix}</li>")
    return "<h2>Evidence</h2><ul>" + "".join(rows) + "</ul>" if rows else ""


def _finding_block(finding: Any) -> str:
    if not isinstance(finding, dict):
        severity = "Medium"
        title = str(finding)
        detail = ""
        scope = ""
        references: list[Any] = []
        finding_id = ""
    else:
        severity = str(finding.get("severity", "Medium"))
        title = str(finding.get("finding", finding.get("title", "Finding")))
        detail = str(finding.get("detail", finding.get("evidence", "")))
        scope = str(finding.get("affected_scope", ""))
        references = finding.get("evidence_refs", []) or []
        finding_id = str(finding.get("id", ""))
    metadata = " · ".join(
        part
        for part in (
            f"ID: {finding_id}" if finding_id else "",
            f"Scope: {scope}" if scope else "",
            f"Evidence: {', '.join(str(item) for item in references)}" if references else "",
        )
        if part
    )
    detail_html = f"<p>{html.escape(_clamp(detail, _MAX_BODY))}</p>" if detail else ""
    metadata_html = (
        f'<div class="small">{html.escape(_clamp(metadata, _MAX_BODY))}</div>'
        if metadata
        else ""
    )
    return (
        '<div class="finding">'
        f'<span class="sev" style="background:{SEVERITY_COLOR.get(severity, "#5a6b7b")}">'
        f"{html.escape(_clamp(severity))}</span>"
        f"<h3>{html.escape(_clamp(title, _MAX_BODY))}</h3>"
        f"{detail_html}{metadata_html}</div>"
    )


def _action_items(actions: list[Any]) -> list[str]:
    result: list[str] = []
    for action in actions:
        if not isinstance(action, dict):
            result.append(str(action))
            continue
        text = str(action.get("action", ""))
        qualifiers = " · ".join(
            part
            for part in (
                str(action.get("priority", "")),
                f"Owner: {action.get('owner')}" if action.get("owner") else "",
                f"Success: {action.get('success_metric')}" if action.get("success_metric") else "",
            )
            if part
        )
        result.append(text + (f" ({qualifiers})" if qualifiers else ""))
    return result


def build_html(data: dict, brand: str = "#0b5fff") -> str:
    if not isinstance(data, dict):
        raise TypeError("agent output must be a dict")
    missing = [key for key in _REQUIRED if key not in data]
    if missing:
        raise ValueError(f"agent output missing required fields: {', '.join(missing)}")
    findings = data.get("findings")
    if findings is not None and not isinstance(findings, list):
        raise ValueError("findings must be a list")

    chart = _score_chart(data.get("scores") or {}, brand)
    finding_html = "".join(_finding_block(item) for item in findings or []) or "<p>No findings recorded.</p>"
    action_html = _listing("Recommended actions", _action_items(data.get("recommended_actions") or []))
    meta = " · ".join(
        filter(
            None,
            [
                html.escape(_clamp(data.get("agent", ""))),
                "Confidence: " + html.escape(_clamp(data.get("confidence", "Unknown"))),
                "Owner: " + html.escape(_clamp(data.get("owner", "—"))),
                "State: " + html.escape(_clamp(data.get("execution_state", "Not recorded"))),
            ],
        )
    )
    chart_html = f'<h2>Scores</h2><img src="{chart}"/>' if chart else ""
    return f"""<!doctype html><html><head><meta charset="utf-8"><style>
@page {{ size: A4; margin: 18mm 16mm; @bottom-center {{ content: "Confidential · " counter(page); font-size:8pt; color:#889; }} }}
body {{ font-family: -apple-system, Segoe UI, Roboto, Arial, sans-serif; color:#1b2733; font-size:10.5pt; }}
.band {{ border-left:6px solid {brand}; padding:2px 0 2px 12px; }}
h1 {{ font-size:19pt; margin:0; }} .meta,.small {{ color:#5a6b7b; font-size:9pt; }}
h2 {{ font-size:13pt; margin:16px 0 6px; border-bottom:1px solid #e6ebf0; padding-bottom:3px; }}
h3 {{ font-size:11pt; margin:4px 0; word-break:break-word; }} img {{ max-width:100%; }}
.finding {{ border:1px solid #e6ebf0; border-radius:6px; padding:10px 12px; margin:8px 0; }}
.sev {{ display:inline-block; color:#fff; font-size:8pt; padding:1px 8px; border-radius:10px; }}
</style></head><body>
<div class="band"><h1>SEO Report</h1><div class="meta">{meta}</div></div>
<h2>Summary</h2><p>{html.escape(_clamp(data.get('summary', ''), _MAX_BODY))}</p>
{_evidence_block(data.get('evidence') or [])}
{chart_html}
<h2>Findings</h2>{finding_html}
{action_html}
{_listing('Dependencies', data.get('dependencies') or [])}
{_listing('Acceptance criteria', data.get('acceptance_criteria') or [])}
{_listing('Verification', _as_list(data.get('verification')))}
{_listing('Risks', data.get('risks') or [])}
<h2>Impact and follow-up</h2><p>{html.escape(_clamp(data.get('impact', 'Not recorded'), _MAX_BODY))}</p>
<p><strong>Follow-up:</strong> {html.escape(_clamp(data.get('follow_up', 'Not recorded'), _MAX_BODY))}</p>
</body></html>"""


def _weasyprint_renderer(markup: str, out: Path) -> None:
    from weasyprint import HTML
    HTML(string=markup).write_pdf(str(out))


def dependency_status() -> dict[str, str]:
    status: dict[str, str] = {}
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


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Render an agent-output JSON as a report")
    parser.add_argument("agent_output")
    parser.add_argument("--out", default=DEFAULT_OUT)
    parser.add_argument("--brand", default="#0b5fff")
    arguments = parser.parse_args()
    print(write_report(load_json(arguments.agent_output), arguments.out, arguments.brand))
