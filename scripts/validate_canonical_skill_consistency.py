"""Validate indexed skill headings and prevent stale duplicate rules from returning."""
from __future__ import annotations
import json,re
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
CATALOG=ROOT/"skills"/"skill-catalog.json"
PROCEDURE_FILES=[ROOT/"skills"/"deep-skill-procedures.md",ROOT/"skills"/"product-proof-procedures.md"]
PROHIBITED={"geo-grid-rank-scan":[r"haversine\s+offset",r"default\s+7x7"],"gbp-profile-audit":[r"25\s+ranking-relevant\s+fields",r"present-and-optimized\s+2"],"cross-platform-nap-verify":[r"name\s+mismatch\s+critical"],"programmatic-seo-governance":[r"warn\s+at\s+30\s+near-duplicate",r"hard\s+stop\s+at\s+50",r"below\s+60%\s+unique",r"below\s+40%"],"competitor-comparison-page-build":[r"min(?:imum)?\s*~?\s*1,?500\s+words",r"generate\s+product/softwareapplication/itemlist\s+schema"]}
def indexed_skills():
 p=json.loads(CATALOG.read_text(encoding="utf-8-sig"));return {str(s) for c in p.get("categories",[]) for s in c.get("skills",[])}
def procedure_sections():
 sections={};heads=[]
 for path in PROCEDURE_FILES:
  if not path.exists():continue
  text=path.read_text(encoding="utf-8");ms=list(re.finditer(r"^## ([a-z0-9-]+)\s*$",text,re.M))
  for i,m in enumerate(ms):
   skill=m.group(1);heads.append(skill);end=ms[i+1].start() if i+1<len(ms) else len(text);sections.setdefault(skill,text[m.start():end])
 return sections,heads
def validate():
 failures=[];indexed=indexed_skills();sections,heads=procedure_sections()
 for s in sorted(indexed-set(sections)):failures.append(f"indexed skill has no deep-procedure heading: {s}")
 for s in sorted(set(sections)-indexed):failures.append(f"deep-procedure heading is not indexed: {s}")
 for s in sorted(set(heads)):
  if heads.count(s)!=1:failures.append(f"deep-procedure heading appears {heads.count(s)} times: {s}")
 for s,patterns in PROHIBITED.items():
  section=sections.get(s,"")
  for pattern in patterns:
   if re.search(pattern,section,re.I):failures.append(f"{s} restores prohibited duplicate rule: {pattern}")
 return failures
def main():
 f=validate()
 if f:
  print("Canonical skill consistency failed:");[print(f"- {x}") for x in f];return 1
 print(f"Canonical skill consistency passed: {len(indexed_skills())} indexed skills, one procedure heading each.");return 0
if __name__=="__main__":raise SystemExit(main())
