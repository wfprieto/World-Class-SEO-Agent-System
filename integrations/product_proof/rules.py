"""Primary-source-bound technical audit rules."""
from __future__ import annotations
import json,re,urllib.parse
from collections import Counter,defaultdict
from pathlib import Path
from typing import Any
from integrations.product_proof.crawler import RobotsPolicy
from integrations.product_proof.models import AgentContribution,Finding

SEV={"Critical":0,"High":1,"Medium":2,"Low":3,"Info":4}; PAGE={"page","paged","pagenum","page_num","pg"}; FACET={"color","size","brand","price","sort","order","filter","material","style","category","availability"}

class ClaimPolicy:
 def __init__(self,path:str|Path):
  raw=json.loads(Path(path).read_text(encoding="utf-8-sig")); self.claims={r["id"]:r for r in raw["claims"]}; self.allowed=set(raw["recommendation_classes"]); self.order=["PRIMARY_SOURCE","CONTROLLED_EXPERIMENT","LARGE_SCALE_OBSERVATIONAL","PRACTITIONER_CONSENSUS","EXPERT_HYPOTHESIS","ANALYSIS","UNVERIFIED","DISPUTED","STALE","FALSE"]
 def claim(self,c):
  if c not in self.claims: raise KeyError(f"unknown SEO claim: {c}")
  return self.claims[c]
 def strongest_class(self,ids):
  kinds={self.claim(c)["evidence_class"] for c in ids}; return min(kinds,key=self.order.index) if kinds else "ANALYSIS"
 def approved_for_recommendation(self,ids): return all(self.claim(c)["evidence_class"] in self.allowed for c in ids)

class TechnicalAuditRules:
 def __init__(self,policy): self.policy=policy; self.findings=[]; self.decisions=[]; self.counts=Counter()
 def add(self,i,t,s,cat,claims,obs,impact,action,verify,urls,owner,state="VERIFIED",confidence="High",missing=None):
  self.counts[i]+=1; fid=i if self.counts[i]==1 else f"{i}-{self.counts[i]}"
  if claims and not self.policy.approved_for_recommendation(claims): state,confidence="REQUIRES_VERIFICATION","Low"
  self.findings.append(Finding(fid,t,s,cat,state,self.policy.strongest_class(claims),claims,obs,impact,action,verify,sorted(set(urls))[:200],owner,confidence,missing_evidence=missing or []))
 @staticmethod
 def dirs(p):
  v=set(p.get("meta_robots",[])); v.update(x.strip().lower() for x in str(p.get("x_robots_tag") or "").split(",") if x.strip()); return v
 @staticmethod
 def paged(u):
  p=urllib.parse.urlsplit(u); return any(k.lower() in PAGE for k in urllib.parse.parse_qs(p.query)) or bool(re.search(r"/(?:page|p)/\d+/?$",p.path,re.I))
 @staticmethod
 def page1(u):
  p=urllib.parse.urlsplit(u); q=[(k,v) for k,v in urllib.parse.parse_qsl(p.query,keep_blank_values=True) if k.lower() not in PAGE]; path=re.sub(r"/(?:page|p)/\d+/?$","/",p.path,flags=re.I); return urllib.parse.urlunsplit((p.scheme,p.netloc,path,urllib.parse.urlencode(q),"")).rstrip("?")
 @staticmethod
 def facet(u): return any(k.lower() in FACET for k in urllib.parse.parse_qs(urllib.parse.urlsplit(u).query))
 def robots(self,c):
  pages=c["pages"]; root=urllib.parse.urlsplit(c["start_url"]); rr=None
  for r in c["robots"]:
   if r["host"]==root.netloc: rr=r
   if r["errors"]: self.add("robots-fetch-failed","robots.txt could not be evaluated","High","Crawl Access",["robots-scope","robots-5xx"],"; ".join(r["errors"]),"Crawler controls are unknown.","Restore a deterministic response.",f"Fetch {r['robots_url']} and record status/body.",[r["robots_url"]],"SEO Diagnostic Infrastructure Agent","MISSING","Low",["robots.txt response"]); continue
   st=int(r["status_code"])
   if st==429 or st>=500: self.add("robots-server-error","robots.txt returns a server-error response","Critical","Crawl Access",["robots-5xx"],f"{r['robots_url']} returned HTTP {st}.","Google can pause crawling or use cached/fallback behavior; asset resources can become ineligible.","Return stable 200 rules or genuine 404.","Confirm stable 200/404.",[r["robots_url"]],"SEO Technical Agent")
   elif 400<=st<500 and st!=429: self.decisions.append({"decision":"robots_4xx_no_restrictions","host":r["host"],"status_code":st,"claim_id":"robots-4xx","interpretation":"Google treats this as no robots restrictions."})
   if r["size_bytes"]>500*1024: self.add("robots-too-large","robots.txt exceeds Google's processing ceiling","High","Crawl Access",["robots-file-limit"],f"{r['size_bytes']} bytes.","Rules after the ceiling can be ignored.","Reduce below 500 KiB.","Refetch and verify size.",[r["robots_url"]],"SEO Technical Agent")
   for u in r["unknown_directives"]:
    f=u.split(":",1)[0].strip().lower()
    if f=="crawl-delay": self.add("robots-crawl-delay","robots.txt uses crawl-delay for Google","Medium","Crawl Access",["robots-crawl-delay-unsupported"],u,"The directive does not control Googlebot.","Remove reliance on crawl-delay.","Reparse robots.txt.",[r["robots_url"]],"SEO Technical Agent")
    if f=="noindex": self.add("robots-noindex","robots.txt contains an unsupported noindex directive","High","Indexability",["robots-disallow-not-noindex"],u,"The index-control instruction is inert.","Use crawlable meta robots or X-Robots-Tag.","Inspect crawl access and page response.",[r["robots_url"]],"SEO Technical Agent")
  if not rr or rr["status_code"]>=400:return
  pol=RobotsPolicy(rr["groups"]); blocked=[p for p in pages if not pol.allowed(p["final_url"])]; ni=[p for p in blocked if "noindex" in self.dirs(p)]
  if ni:self.add("noindex-blocked-by-robots","Pages carry noindex instructions that Google may be unable to read","Critical","Indexability",["robots-disallow-not-noindex"],f"{len(ni)} disallowed page(s) carry noindex.","Blocking can make deindexing instructions unreadable.","Allow crawl access when noindex is intended.","Test robots and page directives.",[p["final_url"] for p in ni],"SEO Technical Agent")
  assets=[a for p in pages for a in p.get("asset_urls",[]) if urllib.parse.urlsplit(a).netloc==root.netloc and not pol.allowed(a)]
  if assets:self.add("blocked-render-assets","robots.txt blocks same-host rendering assets","High","Rendering",["robots-disallow-not-noindex"],f"{len(set(assets))} asset URL(s) blocked.","Pages may render incompletely.","Allow required rendering resources.","Render representative pages.",assets,"SEO Diagnostic Infrastructure Agent")
 def statuses(self,c):
  p=c["pages"]; err=[x for x in p if x["status_code"]==429 or x["status_code"]>=500]; miss=[x for x in p if x["status_code"] in {404,410}]; soft=[x for x in p if x.get("soft_404_signal")]; red=[x for x in p if x["requested_url"]!=x["final_url"]]
  if err:self.add("server-errors","Crawled URLs return server-overload or server-error responses","Critical","Availability",["http-429-server-signal"],f"{len(err)} URL(s) returned 429/5xx.","Persistent failures can reduce crawling and index retention.","Resolve capacity, application, proxy, or origin failures.","Recrawl and monitor.",[x["final_url"] for x in err],"SEO Diagnostic Infrastructure Agent")
  if miss:self.add("missing-linked-pages","The crawl discovered URLs that return 404 or 410","High","Internal Links",["http-404-410"],f"{len(miss)} URL(s) return 404/410.","Important retired URLs can lose traffic/links; internal links create dead ends.","Keep genuine removals, redirect only to equivalents, and update internal links.","Recrawl and verify references.",[x["final_url"] for x in miss],"SEO Information Architecture Agent")
  if soft:self.add("soft-404","Successful responses contain missing or near-empty page signals","High","Index Quality",["soft-404"],f"{len(soft)} 2xx page(s) appear missing/empty.","Soft 404s create misleading index states.","Return genuine 404/410 or restore content.","Verify status/content and Search Console.",[x["final_url"] for x in soft],"SEO Technical Agent")
  if red:self.add("internal-redirects","The crawl followed internally discovered redirecting URLs","Medium","Internal Links",["http-redirect-signals"],f"{len(red)} URL(s) redirected.","Redirects add latency and obscure preferred URLs.","Update internal links to final destinations.","Recrawl for direct links.",[x["requested_url"] for x in red],"SEO Information Architecture Agent")
 def canon(self,c):
  p=c["pages"]; by={x["final_url"]:x for x in p}; ns=[x for x in p if x.get("canonical") and x["canonical"]!=x["final_url"]]; broken=[x for x in ns if x["canonical"] in by and not 200<=by[x["canonical"]]["status_code"]<300]
  if broken:self.add("canonical-broken-target","Canonical targets return non-success responses","Critical","Canonicalization",["canonical-strength"],f"{len(broken)} page(s) target non-2xx canonicals.","Invalid targets prevent reliable consolidation.","Point to stable indexable 2xx URLs.","Recrawl source and target.",[x["final_url"] for x in broken],"SEO Technical Agent")
  chains=[]; cycles=[]
  for x in ns:
   origin=x["final_url"]; cur=x["canonical"]; seen={origin}; depth=0
   while cur in by and by[cur].get("canonical"):
    depth+=1
    if cur in seen:cycles.append(origin);break
    seen.add(cur); nxt=by[cur]["canonical"]
    if nxt==cur:break
    cur=nxt
    if depth>=20:break
   if depth>1 and origin not in cycles:chains.append(origin)
  if cycles:self.add("canonical-cycle","Canonical signals form a cycle","Critical","Canonicalization",["canonical-strength"],f"{len(set(cycles))} cycle origin(s).","Conflicting consolidation instructions.","Choose one preferred URL and point duplicates directly.","Confirm an acyclic graph.",cycles,"SEO Technical Agent")
  if chains:self.add("canonical-chain","Canonical annotations form multi-hop chains","High","Canonicalization",["canonical-strength"],f"{len(set(chains))} chain origin(s).","Indirect signals add ambiguity.","Point duplicates directly to final canonical.","Confirm one-hop targets.",chains,"SEO Technical Agent")
  bad=[x["final_url"] for x in p if self.paged(x["final_url"]) and x.get("canonical")==self.page1(x["final_url"])]
  if bad:self.add("pagination-canonical-page-one","Paginated pages canonicalize to page one","Critical","Pagination",["pagination-self-canonical"],f"{len(bad)} paginated page(s) target page one.","Deep content can be excluded from discovery/indexing.","Use unique URLs, self-canonicals, and anchor links.","Crawl the full sequence.",bad,"SEO Information Architecture Agent")
  legacy=[x["final_url"] for x in p if x.get("rel_next") or x.get("rel_prev")]
  if legacy:self.add("pagination-legacy-rel","Pages depend on legacy rel=next/prev annotations","Low","Pagination",["rel-next-prev-dead","pagination-real-links"],f"{len(legacy)} page(s) include legacy annotations.","They are not a current Google pagination signal.","Ensure real anchor pagination and self-canonicals.","Crawl without relying on annotations.",legacy,"SEO Information Architecture Agent")
  dup={x["final_url"] for x in ns}; links=[t for x in p for t in x["internal_links"] if t in dup]
  if links:self.add("links-to-noncanonical","Internal links point to noncanonical URL variants","High","Internal Links",["canonical-link-consistency"],f"{len(set(links))} noncanonical targets receive links.","The graph contradicts canonical preferences.","Link to preferred canonicals.","Recrawl and verify targets.",links,"SEO Information Architecture Agent")
 def ai_cwv_facets(self,c):
  p=c["pages"]; no=[x["final_url"] for x in p if "nosnippet" in self.dirs(x)]; mx=[x["final_url"] for x in p if any(v.startswith("max-snippet") for v in self.dirs(x))]
  if no:self.add("nosnippet-tradeoff","Pages use nosnippet, affecting normal snippets and Google AI features","Medium","AI Extraction Controls",["nosnippet-ai-input"],f"{len(no)} page(s) use nosnippet.","Normal snippets and Google AI direct input are suppressed.","Confirm the business trade-off; do not remove automatically.","Review directive and search presentation.",no,"SEO Compliance & Legal Agent")
  if mx:self.add("maxsnippet-tradeoff","Pages cap snippet and Google AI direct-input length","Info","AI Extraction Controls",["max-snippet-ai-input"],f"{len(mx)} page(s) use max-snippet.","The cap can limit extraction and normal presentation.","Document rationale and test approved changes.","Compare search presentation.",mx,"SEO Compliance & Legal Agent")
  lazy=[]; dims=[]
  for x in p:
   for im in x.get("images",[])[:2]:
    if str(im.get("loading") or "").lower()=="lazy":lazy.append(x["final_url"])
    if not im.get("width") or not im.get("height"):dims.append(x["final_url"])
  if lazy:self.add("likely-lcp-lazy","Early page images are lazy-loaded and may include the LCP element","High","Core Web Vitals",["lcp-no-lazy","lcp-subparts"],f"{len(set(lazy))} page(s) lazy-load an early image.","If it is LCP, lazy loading adds resource delay.","Confirm LCP and remove lazy loading only when verified.","Measure LCP subparts.",lazy,"SEO Diagnostic Infrastructure Agent","STRONGLY_SUPPORTED","Medium",["Actual browser-measured LCP element"])
  if dims:self.add("image-dimensions","Early images lack explicit dimensions","Medium","Core Web Vitals",["cwv-thresholds"],f"{len(set(dims))} page(s) lack image dimensions.","Missing reserved space can contribute to CLS.","Provide dimensions or aspect-ratio reservation.","Measure CLS.",dims,"SEO Diagnostic Infrastructure Agent")
  facets=[x for x in p if self.facet(x["final_url"])]; empty=[x for x in facets if 200<=x["status_code"]<300 and x.get("soft_404_signal")]
  if empty:self.add("facet-empty-200","Empty faceted combinations return successful responses","High","Faceted Navigation",["facets-empty-404","soft-404"],f"{len(empty)} empty-looking facets return 2xx.","Low-value URL spaces can expand.","Return genuine 404 for empty combinations.","Test representative combinations.",[x["final_url"] for x in empty],"SEO E-commerce Agent")
  orders=defaultdict(list)
  for x in facets:
   ks=tuple(k.lower() for k,_ in urllib.parse.parse_qsl(urllib.parse.urlsplit(x["final_url"]).query));orders[tuple(sorted(ks))].append("&".join(ks))
  if any(len(set(v))>1 for v in orders.values()):self.add("facet-order-inconsistent","Equivalent facet parameters appear in inconsistent orders","Medium","Faceted Navigation",["facets-parameter-separator"],"Equivalent parameter sets have multiple orders.","Duplicate URL forms can expand inventory.","Normalize order and duplicate filters.","Regenerate facet inventory.",[x["final_url"] for x in facets],"SEO E-commerce Agent")
  n=len(p);self.decisions.append({"decision":"crawl_budget_materiality","status":"NOT_DEMONSTRATED" if n<10000 else "REQUIRES_SCALE_REVIEW","observed_crawl_size":n,"claim_id":"crawl-budget-scale","interpretation":"This bounded crawl does not establish a material crawl-budget constraint." if n<10000 else "Separate large-site review is warranted."})
 def evaluate(self,c):
  self.robots(c);self.statuses(c);self.canon(c);self.ai_cwv_facets(c);self.findings.sort(key=lambda x:(SEV[x.severity],x.category,x.id));g=defaultdict(list)
  for f in self.findings:g[f.category].append(f.id)
  return {"findings":[f.to_dict() for f in self.findings],"decisions":self.decisions,"root_cause_groups":[{"category":k,"finding_ids":v,"finding_count":len(v)} for k,v in sorted(g.items())]}

def build_contributions(c,r):
 f=r["findings"];o=Counter(x["owner"] for x in f);e=len(c["pages"])+len(c["robots"])
 rows=[
  AgentContribution("SEO Diagnostic Infrastructure Agent","bounded collection and performance evidence",e,o["SEO Diagnostic Infrastructure Agent"],o["SEO Diagnostic Infrastructure Agent"],0,0,0,"Created the canonical crawl dataset and isolated transport failures."),
  AgentContribution("SEO Technical Agent","crawl, status, canonical and robots rules",len(c["pages"]),o["SEO Technical Agent"],o["SEO Technical Agent"],0,0,len(r["decisions"]),"Applied primary-source rules without index or ranking assumptions."),
  AgentContribution("SEO Information Architecture Agent","internal graph and pagination",sum(len(x["internal_links"]) for x in c["pages"]),o["SEO Information Architecture Agent"],o["SEO Information Architecture Agent"],0,0,0,"Connected URL symptoms into graph and pagination root causes."),
  AgentContribution("SEO Compliance & Legal Agent","AI extraction trade-off review",sum(1 for x in c["pages"] if x["meta_robots"] or x["x_robots_tag"]),o["SEO Compliance & Legal Agent"],o["SEO Compliance & Legal Agent"],0,0,0,"Kept extraction controls approval-gated."),
  AgentContribution("SEO Full Audit/Analyst Agent","root-cause consolidation",len(f),len(f),len(f),max(len(f)-len(r["root_cause_groups"]),0),0,len(r["decisions"]),"Consolidated symptoms into client-actionable root causes."),
  AgentContribution("SEO Scrummaster Agent","evidence challenge gate",0,0,sum(x["evidence_state"]!="REQUIRES_VERIFICATION" for x in f),0,sum(x["evidence_state"]=="REQUIRES_VERIFICATION" for x in f),len(r["decisions"]),"Blocked unsupported claims and retained open evidence gaps."),
  AgentContribution("SEO Output Report Agent","client and engineering deliverables",len(f),0,len(f),0,0,0,"Translated evidence into impact, ownership, and verification instructions.")]
 return [x.to_dict() for x in rows]
