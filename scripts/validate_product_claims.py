"""Validate public product wording against the canonical product-claim inventory."""
from __future__ import annotations
import json
from pathlib import Path
from typing import Any
ROOT=Path(__file__).resolve().parents[1]
def _json(path:Path)->Any:return json.loads(path.read_text(encoding="utf-8-sig"))
def validate(root:Path=ROOT)->list[str]:
 payload=_json(root/"knowledge"/"product-claim-inventory.json");fail=[];ids=set();allowed={"APPROVED","APPROVED_WITH_QUALIFIER","BLOCKED"}
 for row in payload.get("claims",[]):
  cid=str(row.get("id",""))
  if not cid or cid in ids:fail.append(f"duplicate or missing product claim id: {cid!r}")
  ids.add(cid)
  if row.get("status") not in allowed:fail.append(f"{cid}: invalid status")
  for field in ("public_claim","required_proof","approved_wording","prohibited_wording"):
   if not row.get(field):fail.append(f"{cid}: missing {field}")
  if row.get("status")=="BLOCKED" and row.get("approved_wording")==row.get("public_claim"):fail.append(f"{cid}: blocked claim repeats unqualified wording")
 readiness=_json(root/"evaluation"/"comparative"/"final-release-readiness.json")
 if readiness.get("release_decision")!="BLOCKED":fail.append("release readiness must remain BLOCKED until external gates pass")
 return fail
def main():
 f=validate(ROOT);print(json.dumps({"status":"ok" if not f else "failed","failures":f},indent=2));return 0 if not f else 1
if __name__=="__main__":raise SystemExit(main())
