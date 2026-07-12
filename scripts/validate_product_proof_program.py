"""Twenty-pass APIVR validation for the evidence-driven product rebuild."""
from __future__ import annotations
import json
from pathlib import Path
from typing import Callable
ROOT=Path(__file__).resolve().parents[1]
def _json(path:Path):return json.loads(path.read_text(encoding="utf-8-sig"))
def validate(root:Path=ROOT)->dict:
 rows=_json(root/"evaluation"/"product-proof"/"requirements.json")["requirements"];fail=[];passes=[]
 def record(name:str,check:Callable[[],tuple[bool,str]]):
  ok,detail=check();passes.append({"pass":str(len(passes)+1),"name":name,"status":"PASS" if ok else "FAIL","detail":detail})
  if not ok:fail.append(f"{name}: {detail}")
 ids=[r["id"] for r in rows]
 record("Requirement identity",lambda:(len(ids)==len(set(ids)),f"{len(ids)} unique requirements"))
 record("Source traceability",lambda:(all(r.get("source_sections") for r in rows),"Every requirement names report sections"))
 record("Status vocabulary",lambda:(all(r["status"] in {"IMPLEMENTED","PLANNED_NEXT_INCREMENT","BLOCKED_EXTERNAL_EVIDENCE"} for r in rows),"No ambiguous completion state"))
 record("Implemented artifacts",lambda:(all(all((root/p).exists() for p in r["implementation"]) for r in rows if r["status"]=="IMPLEMENTED"),"Every implemented requirement has existing artifacts"))
 record("Implemented tests",lambda:(all(r.get("tests") for r in rows if r["status"]=="IMPLEMENTED"),"Every implemented requirement names tests"))
 record("External blockers explicit",lambda:(all(r.get("blocker") for r in rows if r["status"]!="IMPLEMENTED"),"No deferred requirement is silently omitted"))
 checks=[("Claim registry","knowledge/seo-claim-registry.json"),("Deprecation registry","knowledge/deprecation-registry.json"),("Primary source pack","knowledge/primary-source-technical-seo.md"),("Bounded crawler","integrations/product_proof/crawler.py"),("Rule engine","integrations/product_proof/rules.py"),("Root-cause reporting","integrations/product_proof/report.py"),("CLI product path","seoctl/audit_cli.py"),("Command overlay","seoctl/command-registry-overlay.json"),("Capability overlay","orchestration/product-proof-capability-overlay.json")]
 for name,path in checks:record(name,lambda p=path:((root/p).exists(),f"{p} exists"))
 record("Artifact manifest",lambda:("run-manifest.json" in (root/"integrations/product_proof/service.py").read_text(encoding="utf-8"),"Service writes a manifest"))
 record("Agent contribution ledger",lambda:("agent-contributions.json" in (root/"integrations/product_proof/service.py").read_text(encoding="utf-8"),"Contribution artifact is mandatory"))
 record("Skill convergence",lambda:((root/"skills/product-proof-technical-audit.md").exists() and (root/"skills/product-proof-procedures.md").exists(),"Skill and procedure extension exist"))
 record("Feedback loops",lambda:((root/"evaluation/product-proof/feedback-learning-loop.json").exists() and (root/"evaluation/product-proof/feedback-optimization-loop.json").exists(),"Learning and optimization records exist"))
 blocked=[r["id"] for r in rows if r["status"]=="BLOCKED_EXTERNAL_EVIDENCE"]
 record("Release truth",lambda:(bool(blocked),f"External proof remains blocked and explicit: {', '.join(blocked)}"))
 return {"status":"PASS" if not fail else "FAIL","passes":passes,"failures":fail,"implemented":sum(r["status"]=="IMPLEMENTED" for r in rows),"planned_next_increment":sum(r["status"]=="PLANNED_NEXT_INCREMENT" for r in rows),"blocked_external_evidence":sum(r["status"]=="BLOCKED_EXTERNAL_EVIDENCE" for r in rows),"release_approved":False,"note":"Implementation validation does not satisfy authorized live-site, external-review, CI-observability, or public-release gates."}
def main():
 r=validate(ROOT);print(json.dumps(r,indent=2));return 0 if r["status"]=="PASS" else 1
if __name__=="__main__":raise SystemExit(main())
