"""Validate claim precedence, external wording, and deprecated SEO guidance."""
from __future__ import annotations
import argparse,json,re
from datetime import date
from pathlib import Path
from typing import Any
ROOT=Path(__file__).resolve().parents[1]
VALID_CLASSES={"PRIMARY_SOURCE","CONTROLLED_EXPERIMENT","LARGE_SCALE_OBSERVATIONAL","PRACTITIONER_CONSENSUS","EXPERT_HYPOTHESIS","ANALYSIS","UNVERIFIED","DISPUTED","STALE","FALSE"}
def _json(path:Path)->Any:return json.loads(path.read_text(encoding="utf-8-sig"))
def validate(root:Path=ROOT,*,as_of:date|None=None)->list[str]:
 today=as_of or date.today();claims=_json(root/"knowledge"/"seo-claim-registry.json");deps=_json(root/"knowledge"/"deprecation-registry.json");fail=[];seen=set()
 for row in claims.get("claims",[]):
  cid=row.get("id")
  if not cid or cid in seen:fail.append(f"duplicate or missing claim id: {cid!r}")
  seen.add(str(cid));ev=row.get("evidence_class")
  if ev not in VALID_CLASSES:fail.append(f"{cid}: invalid evidence class {ev!r}")
  for field in ("claim","source_section","verified_at","review_by","public_wording","prohibited_wording"):
   if not row.get(field):fail.append(f"{cid}: missing {field}")
  try:
   review=date.fromisoformat(row["review_by"])
   if review<today and ev=="PRIMARY_SOURCE":fail.append(f"{cid}: primary-source review is overdue ({review})")
  except (KeyError,ValueError):fail.append(f"{cid}: invalid review_by date")
  if ev in {"UNVERIFIED","DISPUTED","STALE","FALSE"} and row.get("source_url") and row["public_wording"]==row["claim"]:fail.append(f"{cid}: blocked evidence repeats the raw claim as approved wording")
 dep_ids=set()
 for row in deps.get("entries",[]):
  if row.get("id") in dep_ids:fail.append(f"duplicate deprecation id: {row.get('id')}")
  dep_ids.add(row.get("id"))
  if row.get("state") not in {"STALE","FALSE"}:fail.append(f"{row.get('id')}: invalid deprecation state")
  if not row.get("prohibited") or not row.get("replacement"):fail.append(f"{row.get('id')}: missing prohibited or replacement")
 maintained=[root/"docs"/"PRODUCT-PROOF-TECHNICAL-AUDIT.md",root/"skills"/"product-proof-technical-audit.md",root/"skills"/"product-proof-intelligence-skills.md",root/"knowledge"/"primary-source-technical-seo.md",*[root/"knowledge"/"source-assets"/n for n in ["core-web-vitals-remediation.md","ai-search-and-retrieval.md","content-information-gain.md","authority-brand-and-links.md","local-reviews-compliance.md","client-reporting-roi.md","measurement-and-attribution.md"]]]
 bans={"FID is a Core Web Vital":"fid-core-web-vital","Google My Business":"google-my-business","meta keywords improve":"meta-keywords","Google requires rel=next":"rel-next-prev-google","crawl-delay controls Google":"crawl-delay-google"}
 for path in maintained:
  if not path.exists():fail.append(f"missing maintained product-proof file: {path.relative_to(root)}");continue
  text=path.read_text(encoding="utf-8")
  for phrase,did in bans.items():
   if re.search(re.escape(phrase),text,re.I):fail.append(f"{path.relative_to(root)} restores deprecated guidance {did}: {phrase}")
 return fail
def main():
 p=argparse.ArgumentParser();p.add_argument("--root",type=Path,default=ROOT);a=p.parse_args();f=validate(a.root.resolve())
 if f:print(json.dumps({"status":"failed","failures":f},indent=2));return 1
 print(json.dumps({"status":"ok","claims":len(_json(a.root.resolve()/"knowledge"/"seo-claim-registry.json")["claims"])},indent=2));return 0
if __name__=="__main__":raise SystemExit(main())
