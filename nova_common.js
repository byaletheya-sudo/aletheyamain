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
