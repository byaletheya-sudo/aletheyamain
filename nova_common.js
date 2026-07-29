/* Nova Admins · shared helpers — loaded once, cached, used by every suite page. */
function esc(s){ return String(s==null?"":s).replace(/&/g,"&amp;").replace(/"/g,"&quot;").replace(/</g,"&lt;"); }
function lsGet(k){ try{return localStorage.getItem(k);}catch(e){return null;} }
function lsSet(k,v){ try{localStorage.setItem(k,v);}catch(e){} }
function markSaved(s,cls){ const el=document.getElementById("saveTag"); if(!el)return; el.textContent=s; el.className="save-tag "+cls; }
// Row-level write to the shared store (upsert/delete one deal/agent/expense/task/note by id).
async function saveRow(payload){
  if(location.protocol==="file:")return;
  markSaved("Saving…","saving");
  try{ const r=await fetch("/nova-admins/mutate",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(payload)});
    markSaved(r.ok?"✓ Saved":"Save failed", r.ok?"ok":"err"); }
  catch(e){ markSaved("Save failed — offline","err"); }
}

// ---- MONEY ENGINE (moved here from nova_admins.html so every suite page shares it) ----
// Kept in lockstep with _nova_calc in server.py — change both together.
// Pages must set window.AGENTS to the store's agents array before calling calc().
function naAgent(id){ return (window.AGENTS||[]).find(function(a){ return a.id===id; }); }
// Stripe: a stored fee > 0 wins (imported/manual). But a stored 0/blank does NOT
// zero it out on a Stripe deal — even when "the client covered the fee", we still
// pay ~3% processing on the charge, so the auto 3% of front applies.
// Stripe is a FRONT-END charge only — the client pays their front on a card. The
// back end is the dealer paying Nova (Check/ACH/Wire/Zelle), never Stripe. So the
// 3% processing fee is 3% of the front when pay==="Stripe". A manual total > 0 overrides.
function feeStripe(d){ const v=d.feeStripe;
  if(v!==undefined && v!==null && v!=="" && (+v||0)>0) return +v;
  return d.pay==="Stripe" ? Math.round((+d.front||0)*0.03) : 0; }
// Envy: automatic 20% of the back end when a back exists. Applies to every deal
// dated ENVY_START or later (Edgar: retroactive for July 2026 + everything
// forward) — date-based so it survives Imports. A typed number overrides; deals
// before the start date stay at 0 so reconciled history (Jan–Jun) doesn't shift.
const ENVY_START="2026-07-01";
function envyEligible(d){ return ("feeEnvy" in d) || (d.date||"")>=ENVY_START; }
function feeEnvy(d){
  if(("feeEnvy" in d) && d.feeEnvy!=="" && d.feeEnvy!==null && d.feeEnvy!==undefined) return +d.feeEnvy||0;  // manual override
  if(!envyEligible(d)) return 0;                                    // pre-July legacy — untouched
  return (+d.back||0)>0 ? Math.round((+d.back)*0.20) : 0; }         // auto · 20% of back
// Shared fees = costs that reduce the split pool (agent + Nova both share them). Envy
// is NOT here — it's a NOVA-ONLY cost: Envy receives the back end, keeps 20% (Nova eats
// it), and forwards 80% to Nova. It's subtracted from Nova's take below, so it never
// touches the agent's split.
function feesTotal(d){ return feeStripe(d) + (+d.feeReferral||0) + (+d.feeProgram||0); }
function calc(d){
  const combined = (+d.front||0) + (+d.back||0);
  const fees = feesTotal(d);                            // Jason + Stripe(auto) + Referral
  const netPool = combined - fees;
  const _ag=naAgent(d.agentId); const pct=(_ag&&_ag.pct&&_ag.pct[d.lead])||0;
  // Per-side nets, so each side can be paid as its cash lands. EVERY shared fee — Stripe
  // (3% of the client's card charge), Referral, and Program (incl. legacy Jason, e.g.
  // Jason Ma) — comes entirely off the FRONT, never the back. The back end is the dealer
  // paying Nova; these fees are all deducted from the client's front payment (Edgar, July
  // 2026). Only when there is no front at all do the fees fall to the back.
  const _feesF = (+d.front||0)>0 ? fees : 0;   // all shared fees ride the front (unless there's no front)
  const frontNet = combined ? (+d.front||0) - _feesF : 0;
  const backNet  = combined ? (+d.back||0) - (fees - _feesF) : 0;
  let agentCut = netPool * pct/100;
  let overridden = false;
  if(d.override!=null){ agentCut = d.override; overridden = true; }
  const ratio = (agentCut) / (netPool||1);             // effective share (after override)
  const agentFront = frontNet * ratio, agentBack = backNet * ratio;
  const envy = feeEnvy(d);                               // 20% of back — Envy keeps this; Nova eats it
  const novaPool = netPool - agentCut;                   // Nova's share of the split pool
  const novaCut = novaPool - envy;                       // Nova take = pool share − Envy's 20% cut
  return {combined, fees, feeStripe:feeStripe(d), feeEnvy:envy, feeProgram:+d.feeProgram||0, netPool, pct, frontNet, backNet, agentCut, novaPool, novaCut, agentFront, agentBack, overridden,
          splitPct: netPool? Math.round(agentCut/netPool*100):0};
}

// ---- CRM/lease-book shared helpers ----
// Month math with day-of-month clamping (Jan 31 + 1mo → Feb 28). Kept in lockstep with
// _add_months in server.py — change both together.
function naAddMonths(ymdStr, n){
  var p = String(ymdStr||"").split("-").map(Number);
  if(p.length<3 || !p[0]) return "";
  var t = new Date(p[0], p[1]-1+n, 1);
  var last = new Date(t.getFullYear(), t.getMonth()+1, 0).getDate();
  t.setDate(Math.min(p[2], last));
  return t.getFullYear()+"-"+String(t.getMonth()+1).padStart(2,"0")+"-"+String(t.getDate()).padStart(2,"0");
}
// "Luis D." → "luis d" — the ledger's client-name convention normalized for cross-deal matching.
function naNormName(s){ return String(s||"").toLowerCase().replace(/\./g,"").replace(/\s+/g," ").trim(); }
// whole calendar months from a → b (negative when b is earlier); day-of-month respected
function naMonthDiff(a, b){
  var pa=String(a).split("-").map(Number), pb=String(b).split("-").map(Number);
  var m=(pb[0]-pa[0])*12+(pb[1]-pa[1]);
  if(pb[2]<pa[2]) m--;
  return m;
}
function naPhoneKey(p){ return String(p||"").replace(/\D/g,"").slice(-10); }

// ---- THE LEASE BOOK (CRM build F2/F5/F6/F7) ----
// ONE central derivation shared by every consumer: live deals + historic deals + the
// mutable leasebook overlay in, one lease record per deal out. All maturity/renewal
// logic lives HERE — tabs and pages render the book, they never re-derive it.
//
// Renewal matching is name-based ("First L." convention): a renewal is ANY later deal
// (lease or buy) by the same normalized client name closing from 2 months before this
// lease's maturity onward — no upper cutoff, late returners count. Confidence: "high"
// (auto-linked) needs exactly one candidate and no conflicting phone/email between the
// two deals; anything ambiguous is "medium" → the review queue, never auto-linked.
// Overlay renewalLink / renewalRejects are Edgar's word and always win.
function naLeaseBook(liveDeals, histDeals, overlay, today){
  var ov={}; (overlay||[]).forEach(function(o){ if(o&&o.id) ov[o.id]=o; });
  var rows=[];
  (histDeals||[]).forEach(function(d){ if(d&&d.date) rows.push({ref:"H"+d.id, src:"hist", deal:d}); });
  (liveDeals||[]).forEach(function(d){ if(d&&d.date) rows.push({ref:"L"+d.id, src:"live", deal:d}); });
  var byName={};
  rows.forEach(function(r){ r.norm=naNormName(r.deal.client); if(r.norm)(byName[r.norm]=byName[r.norm]||[]).push(r); });
  var out = rows.map(function(r){
    var d=r.deal, o=ov[r.ref]||{};
    var kind = d.type==="Buy" ? "financed" : "lease";
    var term = +d.term||0, termAssumed = kind==="lease" && !term;
    // financed deals have no maturity — 24-month outreach cycle instead (build doc rule)
    var cycle = kind==="financed" ? 24 : (term||36);
    var natural = naAddMonths(d.date, cycle);
    var maturity = o.maturityOverride || (o.closedEarly && o.closedEarlyDate) || natural;
    var status = o.closedEarly ? "closedEarly" : (maturity<=today ? "matured" : "active");
    var mtm = naMonthDiff(today, maturity);
    var urgency = status!=="active" ? "past" : (mtm>=12 ? "green" : mtm>=6 ? "yellow" : "red");
    var flags=[];
    if(termAssumed) flags.push("term_assumed");
    if(!((d.phone||"").trim()||(d.email||"").trim())) flags.push("no_contact");
    return {ref:r.ref, src:r.src, deal:d, client:d.client||"", normName:r.norm,
      phone:d.phone||"", email:d.email||"", agentId:d.agentId, brand:d.make||"",
      vehicle:[d.year,d.make,d.model].filter(Boolean).join(" "),
      dealer:d.dealer||"", kind:kind, closeDate:d.date, term:term||null, termAssumed:termAssumed,
      cycle:cycle, maturity:maturity, natural:natural, status:status,
      monthsToMaturity:mtm, urgency:urgency,
      outreach:o.outreach||"not_started", overlay:o, flags:flags, renewal:{state:"none"}};
  });
  var byRef={}; out.forEach(function(x){ byRef[x.ref]=x; });
  out.forEach(function(x){
    var o=x.overlay;
    if(o.renewalLink && byRef[o.renewalLink]){
      var m0=byRef[o.renewalLink];
      x.renewal={state:"confirmed", matchRef:m0.ref, matchDate:m0.closeDate, matchAgentId:m0.agentId, confidence:"high"};
      return;
    }
    // ANY later deal by the same name is a candidate. In-window (maturity−2mo onward,
    // no upper cutoff) = a renewal; earlier than that = an EARLY repeat — the build-doc
    // rule is to close the old lease early once Edgar confirms it's the same person,
    // so early candidates always land in review, never auto-link.
    var windowStart=naAddMonths(x.maturity,-2);
    var cands=(byName[x.normName]||[]).filter(function(r){
      return r.ref!==x.ref && r.deal.date>x.closeDate &&
             !(o.renewalRejects||[]).includes(r.ref);
    }).sort(function(a,b){ return a.deal.date<b.deal.date?-1:1; });
    if(!cands.length){ x.renewal={state:(o.renewalRejects&&o.renewalRejects.length)?"rejected":"none"}; return; }
    var m=cands[0], md=m.deal, xd=x.deal;
    var early = md.date < windowStart;
    var pA=naPhoneKey(xd.phone), pB=naPhoneKey(md.phone);
    var eA=String(xd.email||"").toLowerCase().trim(), eB=String(md.email||"").toLowerCase().trim();
    var conflict=(pA&&pB&&pA!==pB)||(eA&&eB&&eA!==eB);
    var corroborated=(pA&&pB&&pA===pB)||(eA&&eB&&eA===eB);
    var high=!conflict && (cands.length===1 || corroborated);
    x.renewal={state:(high&&!early)?"auto":"review", matchRef:m.ref, matchDate:md.date,
               matchAgentId:md.agentId, confidence:high?"high":"medium", early:early};
  });
  return out;
}

// ---- theme: dark / light / auto (auto follows the OS) ----
// Runs from <head>, so the attribute lands on <html> before first paint — no flash.
(function(){
  var KEY="na_theme";
  var mq = window.matchMedia ? matchMedia("(prefers-color-scheme: light)") : null;
  function pref(){ var t=lsGet(KEY); return (t==="light"||t==="auto"||t==="dark") ? t : "dark"; }
  function apply(){
    var t=pref(), eff = t==="auto" ? ((mq&&mq.matches)?"light":"dark") : t;
    document.documentElement.setAttribute("data-theme", eff);
    document.querySelectorAll(".na-thseg button").forEach(function(b){ b.classList.toggle("on", b.dataset.t===t); });
  }
  window.naSetTheme=function(t){ lsSet(KEY,t); apply(); };
  if(mq){ (mq.addEventListener?mq.addEventListener.bind(mq,"change"):mq.addListener.bind(mq))(function(){ if(pref()==="auto") apply(); }); }
  apply();
  // drop the 🌙/☀️/Auto switcher into each page's header (.na-right), left of the save tag
  document.addEventListener("DOMContentLoaded", function(){
    var right=document.querySelector(".na-right"); if(!right) return;
    var seg=document.createElement("div"); seg.className="na-thseg"; seg.title="Theme";
    seg.innerHTML='<button data-t="dark" title="Dark">🌙</button><button data-t="light" title="Light">☀️</button><button data-t="auto" title="Follow the system">Auto</button>';
    seg.addEventListener("click", function(e){ var b=e.target.closest("button"); if(b) naSetTheme(b.dataset.t); });
    right.insertBefore(seg, right.firstChild);
    apply();
  });
})();
