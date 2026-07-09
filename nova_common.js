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
