/* =====================================================================
   Nova Admins · system-wide AGENT widget
   One stickied assistant, injected on every Admin page. Answers from live
   data, navigates anywhere, and (with a confirm) creates/modifies records.
   All classes are prefixed .nva-* and scoped under #nvaRoot so they never
   collide with a page's own scoped "Add by chat" orb. Uses the page's --na-*
   palette with fallbacks so it looks native everywhere.
   ===================================================================== */
(function(){
  if (window.__novaAgentLoaded) return; window.__novaAgentLoaded = true;

  // which page are we on → label + navigation targets
  var P = location.pathname.replace(/\/+$/,"");
  var PAGE = P.endsWith("/tasks") ? "tasks" : P.endsWith("/notes") ? "notes" : "ledger";
  var NAV = {ledger:"/nova-admins", tasks:"/nova-admins/tasks", notes:"/nova-admins/notes"};
  var ME = (window.NOVA_USER && window.NOVA_USER.id) ? window.NOVA_USER : {id:"edgar", name:"Edgar", role:"owner"};
  var UCOLOR = {edgar:"#3a8eef", nema:"#f472b6", arvin:"#8a5cf0"};
  function today(){ var d=new Date(); return d.getFullYear()+"-"+String(d.getMonth()+1).padStart(2,"0")+"-"+String(d.getDate()).padStart(2,"0"); }
  function esc(s){ return String(s==null?"":s).replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;").replace(/"/g,"&quot;"); }
  function nl(s){ return esc(s).replace(/\n/g,"<br>"); }

  // ---------- styles ----------
  var css = `
  #nvaRoot{--c-panel:var(--na-panel,#171922);--c-panel2:var(--na-panel-2,#20232e);--c-bg:var(--na-bg,#0e0f15);
    --c-line:var(--na-line,#262a36);--c-line2:var(--na-line-2,#333a48);--c-fg:var(--na-fg,#e9ecf2);
    --c-mut:var(--na-muted,#8a91a1);--c-blue:var(--na-blue,#3a8eef);--c-green:var(--na-green,#34d399);--c-red:var(--na-red,#f87171);}
  .nva-launch{position:fixed;right:20px;bottom:20px;z-index:2147483000;display:flex;align-items:center;gap:10px;
    padding:9px 15px 9px 10px;border-radius:999px;cursor:pointer;border:1px solid var(--c-line2);
    background:linear-gradient(180deg,rgba(30,33,44,.96),rgba(17,18,25,.96));backdrop-filter:blur(8px);
    box-shadow:0 12px 34px rgba(0,0,0,.5);color:var(--c-fg);font:600 12.5px/1 -apple-system,system-ui,sans-serif;
    transition:transform .15s,box-shadow .15s;-webkit-tap-highlight-color:transparent;}
  .nva-launch:hover{transform:translateY(-2px);box-shadow:0 16px 40px rgba(0,0,0,.6);}
  .nva-launch .nva-lbl{white-space:nowrap;}
  .nva-launch .nva-key{color:var(--c-mut);font-weight:700;font-size:10.5px;border:1px solid var(--c-line);border-radius:5px;padding:2px 5px;}
  @media(max-width:600px){.nva-launch .nva-lbl,.nva-launch .nva-key{display:none;}.nva-launch{padding:10px;right:16px;bottom:16px;}}
  .nva-orb{width:30px;height:30px;border-radius:50%;position:relative;flex:none;
    background:radial-gradient(circle at 34% 28%,#cfe0ff,#3a8eef 46%,#8a5cf0 100%);
    box-shadow:0 0 14px rgba(58,142,239,.55),0 0 26px rgba(138,92,240,.3);animation:nvaFloat 4.2s ease-in-out infinite;}
  .nva-orb::before{content:"";position:absolute;inset:5px 12px auto 6px;height:5px;border-radius:50%;background:rgba(255,255,255,.5);filter:blur(1.5px);transform:rotate(-18deg);}
  .nva-orb.big{width:64px;height:64px;}
  .nva-orb.big::before{inset:9px 26px auto 13px;height:11px;filter:blur(3px);}
  .nva-orb.big::after{content:"";position:absolute;inset:-8px;border-radius:50%;z-index:-1;filter:blur(8px);
    background:conic-gradient(from 0deg,transparent,rgba(138,92,240,.6),transparent 42%,transparent,rgba(58,142,239,.5),transparent 92%);animation:nvaSpin 3.6s linear infinite;}
  .nva-orb.think{animation:nvaPulse .74s ease-in-out infinite;}
  .nva-orb.think::after{animation:nvaSpin 1.1s linear infinite;}
  .nva-orb.listen{box-shadow:0 0 30px rgba(248,113,113,.62),0 0 60px rgba(248,113,113,.4);}
  .nva-orb.done{box-shadow:0 0 30px rgba(52,211,153,.7),0 0 60px rgba(52,211,153,.42);}
  @keyframes nvaFloat{0%,100%{transform:translateY(0)}50%{transform:translateY(-4px)}}
  @keyframes nvaSpin{to{transform:rotate(360deg)}}
  @keyframes nvaPulse{0%,100%{transform:scale(1)}50%{transform:scale(1.09)}}
  .nva-scrim{position:fixed;inset:0;z-index:2147483001;display:none;align-items:center;justify-content:center;padding:20px;
    background:radial-gradient(120% 90% at 50% 0%,rgba(30,26,60,.5),rgba(4,6,10,.8));backdrop-filter:blur(9px);}
  .nva-scrim.show{display:flex;animation:nvaFade .2s ease;}
  @keyframes nvaFade{from{opacity:0}to{opacity:1}}
  .nva-panel{position:relative;width:100%;max-width:560px;max-height:88vh;overflow:auto;text-align:center;
    background:linear-gradient(180deg,var(--c-panel),#111219);border:1px solid var(--c-line2);border-radius:24px;
    box-shadow:0 40px 110px rgba(0,0,0,.72),inset 0 1px 0 rgba(255,255,255,.04);padding:28px 24px 18px;
    animation:nvaRise .28s cubic-bezier(.2,.9,.25,1);}
  .nva-panel::-webkit-scrollbar{width:0;}
  @keyframes nvaRise{from{transform:translateY(14px) scale(.98);opacity:0}to{transform:none;opacity:1}}
  .nva-x{position:absolute;top:14px;right:16px;cursor:pointer;color:var(--c-mut);font-size:15px;width:26px;height:26px;
    border-radius:8px;display:flex;align-items:center;justify-content:center;border:none;background:transparent;}
  .nva-x:hover{background:var(--c-panel2);color:var(--c-fg);}
  .nva-kick{font-size:10px;font-weight:800;letter-spacing:.16em;color:var(--c-mut);text-transform:uppercase;margin-bottom:12px;}
  .nva-orbwrap{display:flex;justify-content:center;margin:2px 0 15px;}
  .nva-say{font:640 15.5px/1.5 -apple-system,system-ui,sans-serif;color:var(--c-fg);margin:0 auto 16px;max-width:420px;min-height:22px;}
  .nva-say .sub{display:block;font-size:12px;font-weight:500;color:var(--c-mut);margin-top:5px;}
  .nva-body{text-align:left;margin-bottom:4px;}
  .nva-chips{display:flex;flex-direction:column;gap:8px;}
  .nva-chip{cursor:pointer;text-align:left;background:var(--c-panel);border:1px solid var(--c-line);border-radius:12px;
    padding:11px 14px;font:500 12.5px/1.4 -apple-system,system-ui,sans-serif;color:var(--c-mut);transition:.13s;}
  .nva-chip:hover{color:var(--c-fg);border-color:var(--c-line2);background:var(--c-panel2);transform:translateY(-1px);}
  .nva-chip b{color:var(--c-fg);font-weight:700;}
  .nva-ans{background:var(--c-panel);border:1px solid var(--c-line);border-radius:14px;padding:14px 16px;
    font:400 13.5px/1.6 -apple-system,system-ui,sans-serif;color:var(--c-fg);white-space:normal;}
  .nva-acts{display:flex;flex-direction:column;gap:9px;}
  .nva-act{display:flex;gap:11px;align-items:flex-start;background:linear-gradient(180deg,var(--c-panel),var(--c-bg));
    border:1px solid var(--c-line);border-radius:13px;padding:12px 13px;animation:nvaRise .3s ease backwards;}
  .nva-act .ic{width:26px;height:26px;border-radius:8px;flex:none;display:flex;align-items:center;justify-content:center;
    font-size:13px;background:var(--c-panel2);border:1px solid var(--c-line);}
  .nva-act .tx{font:600 13px/1.45 -apple-system,system-ui,sans-serif;color:var(--c-fg);}
  .nva-act .tx .op{display:block;font-size:10px;font-weight:800;letter-spacing:.05em;text-transform:uppercase;color:var(--c-mut);margin-bottom:2px;}
  .nva-actions{display:flex;gap:9px;justify-content:flex-end;margin-top:16px;}
  .nva-btn{cursor:pointer;border:none;border-radius:11px;padding:11px 16px;font:700 13px/1 -apple-system,system-ui,sans-serif;
    background:var(--c-blue);color:#fff;transition:.13s;}
  .nva-btn:hover{filter:brightness(1.08);}
  .nva-btn.ghost{background:transparent;border:1px solid var(--c-line);color:var(--c-mut);}
  .nva-btn.ghost:hover{color:var(--c-fg);border-color:var(--c-line2);}
  .nva-done{display:flex;flex-direction:column;gap:7px;}
  .nva-doneln{display:flex;align-items:center;gap:8px;font:500 13px/1.4 -apple-system,system-ui,sans-serif;color:var(--c-fg);}
  .nva-doneln .ck{color:var(--c-green);font-weight:800;}
  .nva-doneln.fail .ck{color:var(--c-red);}
  .nva-input{display:flex;gap:9px;align-items:flex-end;border-top:1px solid var(--c-line);padding-top:15px;margin-top:16px;}
  .nva-input textarea{flex:1;background:var(--c-panel2);border:1px solid var(--c-line);color:var(--c-fg);border-radius:13px;
    padding:12px 14px;font:400 13.5px/1.45 -apple-system,system-ui,sans-serif;resize:none;outline:none;max-height:130px;}
  .nva-input textarea:focus{border-color:var(--c-blue);}
  .nva-mic{cursor:pointer;width:42px;height:42px;border-radius:12px;flex:none;display:flex;align-items:center;justify-content:center;
    border:1px solid var(--c-line);color:var(--c-mut);background:var(--c-panel2);}
  .nva-mic:hover{color:var(--c-fg);border-color:var(--c-line2);}
  .nva-mic.rec{background:rgba(248,113,113,.15);color:var(--c-red);border-color:rgba(248,113,113,.45);animation:nvaMic 1.1s infinite;}
  @keyframes nvaMic{0%,100%{opacity:1}50%{opacity:.45}}
  .nva-send{cursor:pointer;border:none;border-radius:12px;padding:12px 16px;font-size:15px;line-height:1;background:var(--c-blue);color:#fff;flex:none;}
  /* account chip (bottom-left) + menu + password modal */
  .nva-acct{position:fixed;left:18px;bottom:18px;z-index:2147483000;display:flex;align-items:center;gap:8px;padding:6px 13px 6px 6px;border-radius:999px;cursor:pointer;border:1px solid var(--c-line2);background:linear-gradient(180deg,rgba(30,33,44,.96),rgba(17,18,25,.96));backdrop-filter:blur(8px);box-shadow:0 12px 30px rgba(0,0,0,.4);color:var(--c-fg);font:600 12.5px/1 -apple-system,system-ui,sans-serif;transition:transform .15s;}
  .nva-acct:hover{transform:translateY(-2px);}
  .nva-acct .av{width:26px;height:26px;border-radius:50%;color:#fff;font-weight:700;font-size:12px;display:flex;align-items:center;justify-content:center;flex:none;}
  @media(max-width:600px){.nva-acct .nm{display:none;}.nva-acct{padding:6px;left:14px;bottom:14px;}}
  .nva-amenu{position:fixed;left:18px;bottom:62px;z-index:2147483002;width:214px;background:var(--c-panel);border:1px solid var(--c-line2);border-radius:14px;padding:6px;box-shadow:0 24px 60px rgba(0,0,0,.6);display:none;}
  .nva-amenu.show{display:block;}
  .nva-amenu .who{padding:9px 11px 10px;border-bottom:1px solid var(--c-line);margin-bottom:5px;}
  .nva-amenu .who b{display:block;font-size:13px;} .nva-amenu .who span{font-size:11px;color:var(--c-mut);text-transform:capitalize;}
  .nva-amenu .mi{display:block;width:100%;text-align:left;background:none;border:none;color:var(--c-fg);padding:9px 11px;border-radius:8px;font:500 12.5px/1.2 -apple-system,system-ui,sans-serif;cursor:pointer;}
  .nva-amenu .mi:hover{background:var(--c-panel2);}
  .nva-amenu .mi.danger{color:var(--c-red);}
  .nva-acctf{display:flex;flex-direction:column;gap:4px;text-align:left;margin-top:6px;}
  .nva-acctf label{font-size:11px;color:var(--c-mut);font-weight:600;margin-top:6px;}
  .nva-acctf input,.nva-team input{background:var(--c-panel2);border:1px solid var(--c-line);border-radius:10px;padding:11px 13px;color:var(--c-fg);font-size:13px;outline:none;}
  .nva-acctf input:focus,.nva-team input:focus{border-color:var(--c-blue);}
  .nva-team{margin-top:14px;border-top:1px solid var(--c-line);padding-top:12px;text-align:left;}
  .nva-team .row{display:flex;align-items:center;gap:9px;margin-bottom:9px;}
  .nva-team .row .av{width:24px;height:24px;border-radius:50%;color:#fff;font-weight:700;font-size:11px;display:flex;align-items:center;justify-content:center;flex:none;}
  .nva-team .row input{flex:1;padding:8px 10px;font-size:12px;}
  .nva-msg{font-size:12px;margin-top:8px;min-height:16px;}
  /* energy: stop animating when the tab is backgrounded, or the user prefers less motion */
  #nvaRoot.paused .nva-orb,#nvaRoot.paused .nva-orb::after{animation-play-state:paused;}
  @media (prefers-reduced-motion: reduce){ #nvaRoot .nva-orb,#nvaRoot .nva-orb::before,#nvaRoot .nva-orb::after,#nvaRoot .nva-mic.rec{animation:none !important;} }
  `;
  var st=document.createElement("style"); st.textContent=css; document.head.appendChild(st);

  // ---------- DOM ----------
  var root=document.createElement("div"); root.id="nvaRoot";
  root.innerHTML =
   '<div class="nva-launch" id="nvaLaunch" title="Ask the Nova agent (⌘K)">'
   +  '<span class="nva-orb"></span><span class="nva-lbl">Ask Nova</span><span class="nva-key">⌘K</span></div>'
   +'<div class="nva-scrim" id="nvaScrim">'
   +  '<div class="nva-panel" id="nvaPanel">'
   +    '<button class="nva-x" id="nvaX">✕</button>'
   +    '<div class="nva-kick">Nova Agent · '+esc(PAGE)+'</div>'
   +    '<div class="nva-orbwrap"><div class="nva-orb big" id="nvaOrb"></div></div>'
   +    '<div class="nva-say" id="nvaSay"></div>'
   +    '<div class="nva-body" id="nvaBody"></div>'
   +    '<div class="nva-input">'
   +      '<textarea id="nvaText" rows="1" placeholder="Ask anything, or tell me to do something…"></textarea>'
   +      '<button class="nva-mic" id="nvaMic" title="Speak"><svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="9" y="2" width="6" height="12" rx="3"/><path d="M5 11a7 7 0 0 0 14 0M12 18v3M8 21h8"/></svg></button>'
   +      '<button class="nva-send" id="nvaSend">→</button>'
   +    '</div>'
   +  '</div>'
   +'</div>'
   +'<div class="nva-acct" id="nvaAcct" title="Account"><span class="av" style="background:'+(UCOLOR[ME.id]||"#3a8eef")+'">'+esc((ME.name||"?")[0])+'</span><span class="nm">'+esc(ME.name||"")+'</span></div>'
   +'<div class="nva-amenu" id="nvaAmenu"></div>'
   +'<div class="nva-scrim" id="nvaAcctScrim"><div class="nva-panel" id="nvaAcctPanel" style="max-width:420px"></div></div>';
  document.body.appendChild(root);

  var $ = function(id){ return document.getElementById(id); };
  var scrim=$("nvaScrim"), orbEl=$("nvaOrb"), sayEl=$("nvaSay"), bodyEl=$("nvaBody"), ta=$("nvaText");
  var state="idle", pending=[];

  function orb(c){ orbEl.className="nva-orb big"+(c?" "+c:""); }
  function say(m,sub){ sayEl.innerHTML=nl(m)+(sub?'<span class="sub">'+nl(sub)+'</span>':""); }
  // rotating "thinking" status — feels like it's working through the data
  var THINK=["reading the live numbers…","checking the ledger…","lining up the details…","almost there…"];
  var _thinkI=null;
  function startThink(){ var i=0; _thinkI=setInterval(function(){ i=(i+1)%THINK.length; var s=sayEl.querySelector(".sub"); if(s)s.textContent=THINK[i]; },1050); }
  function stopThink(){ if(_thinkI){ clearInterval(_thinkI); _thinkI=null; } }
  // typewriter reveal — streams the answer in word by word
  var _streamT=null;
  function streamInto(el, text){
    if(_streamT){ clearTimeout(_streamT); _streamT=null; }
    var toks=String(text==null?"":text).split(/(\s+)/), i=0, acc="";
    el.innerHTML="";
    (function step(){ if(i>=toks.length){ _streamT=null; return; } acc+=toks[i++]; el.innerHTML=nl(acc); _streamT=setTimeout(step,16); })();
  }

  var GREET=[
    "What do you need? Ask about the numbers, or tell me to do something.",
    "I can see the whole business from here — ask me anything or give me a job.",
    "Numbers, a new deal, a task, a change — just say it."
  ];
  var IDEAS = {
    ledger:[{t:"How much has Nova made this month?",s:"MTD profit + who's driving it"},
            {t:"Which deals still owe us money?",s:"uncollected front/back"},
            {t:"Log a deal:",s:"BMW X5 for Sarah, $2,500 front, Nova lead, Brandon"}],
    tasks: [{t:"What's due this week?",s:"open tasks by date"},
            {t:"Remind Nema to pay agents Friday",s:"new high-priority task"},
            {t:"Take me to the calendar view",s:"jump anywhere"}],
    notes: [{t:"How much has Nova made this month?",s:"ask from any page"},
            {t:"New note: call the BMW dealer",s:"create a note"},
            {t:"Open the deal ledger",s:"jump anywhere"}]
  };
  function reset(){
    state="idle"; pending=[]; orb();
    say("Hey "+(ME.name||"there")+" — "+GREET[Math.floor((Date.now()/1000)%GREET.length)]);
    bodyEl.innerHTML='<div class="nva-chips">'+(IDEAS[PAGE]||IDEAS.ledger).map(function(c){
      return '<button class="nva-chip" data-full="'+esc(c.t+(/[:?]$/.test(c.t)?" ":""))+'"><b>'+esc(c.t)+'</b> — '+esc(c.s)+'</button>';
    }).join("")+'</div>';
    ta.value=""; ta.style.height="auto";
  }
  function open(){ scrim.classList.add("show"); reset(); setTimeout(function(){ta.focus();},60); }
  function close(){ scrim.classList.remove("show"); if(_recOn&&_rec){try{_rec.stop();}catch(e){}} }

  var OP_ICON={create_task:"☑",create_deal:"🚗",create_note:"📝",update_task:"✎",
    complete_task:"✅",update_deal:"✎",mark_deal_collected:"💰",mark_agent_paid:"💸",delete_task:"🗑"};
  var OP_LBL={create_task:"New task",create_deal:"New deal",create_note:"New note",update_task:"Update task",
    complete_task:"Complete task",update_deal:"Update deal",mark_deal_collected:"Mark collected",mark_agent_paid:"Mark agent paid",delete_task:"Delete task"};

  async function send(text){
    text=(text||ta.value||"").trim(); if(!text||state==="thinking") return;
    state="thinking"; orb("think"); say("Thinking…",THINK[0]); startThink(); bodyEl.innerHTML="";
    try{
      var r=await fetch("/nova-admins/agent",{method:"POST",headers:{"Content-Type":"application/json"},
        body:JSON.stringify({text:text, page:PAGE, today:today()})});
      var out=await r.json();
      stopThink();
      if(!r.ok||out.error){ orb(); state="idle"; say("⚠️ "+(out.error||"I couldn't reach my brain just now."),"try again in a moment"); return; }
      ta.value=""; ta.style.height="auto";
      if(out.kind==="navigate"){
        orb(); state="idle"; say(out.reply||"On my way.","taking you there…");
        var dest=NAV[out.navigate_page]||NAV.ledger; var hash=out.navigate_hash||"";
        setTimeout(function(){ if(dest===NAV[PAGE]&&hash){ location.hash=hash; location.reload(); } else { location.href=dest+hash; } }, 700);
        return;
      }
      if(out.kind==="act" && (out.actions||[]).length){
        pending=out.actions; state="review"; orb();
        say(out.reply||"Here's what I'll do.","review, then confirm");
        renderActs(); return;
      }
      // answer (default) — stream it in
      orb(); state="idle"; say("Here's what I found.");
      bodyEl.innerHTML='<div class="nva-ans"></div>';
      streamInto(bodyEl.querySelector(".nva-ans"), out.reply||"—");
    }catch(e){ stopThink(); orb(); state="idle"; say("⚠️ "+e.message); }
  }

  function renderActs(){
    bodyEl.innerHTML='<div class="nva-acts">'+pending.map(function(a){
      return '<div class="nva-act"><span class="ic">'+(OP_ICON[a.op]||"⚙")+'</span>'
        +'<span class="tx"><span class="op">'+esc(OP_LBL[a.op]||a.op)+'</span>'+esc(a.summary||"")+'</span></div>';
    }).join("")+'</div>'
    +'<div class="nva-actions"><button class="nva-btn ghost" id="nvaCancel">Cancel</button>'
    +'<button class="nva-btn" id="nvaConfirm">✓ Confirm '+pending.length+" action"+(pending.length>1?"s":"")+'</button></div>';
    $("nvaCancel").onclick=reset;
    $("nvaConfirm").onclick=confirmActs;
  }

  async function confirmActs(){
    if(!pending.length) return;
    state="thinking"; orb("think"); say("Doing it…"); bodyEl.innerHTML="";
    try{
      var r=await fetch("/nova-admins/agent/apply",{method:"POST",headers:{"Content-Type":"application/json"},
        body:JSON.stringify({actions:pending})});
      var out=await r.json();
      if(!r.ok||out.error){ orb(); state="review"; say("⚠️ "+(out.error||"Couldn't apply that."),"nothing was changed"); renderActs(); return; }
      var res=out.results||[]; var ok=res.filter(function(x){return x.ok;});
      orb("done"); state="done";
      say("Done — "+ok.length+" change"+(ok.length>1?"s":"")+" applied.");
      bodyEl.innerHTML='<div class="nva-done">'+res.map(function(x){
        return '<div class="nva-doneln'+(x.ok?"":" fail")+'"><span class="ck">'+(x.ok?"✓":"✕")+'</span>'
          +esc((OP_LBL[x.op]||x.op)+(x.label?" · "+x.label:"")+(x.error?" — "+x.error:""))+'</span></div>';
      }).join("")+'</div>'
      +'<div class="nva-actions"><button class="nva-btn ghost" id="nvaMore">+ More</button>'
      +'<button class="nva-btn" id="nvaView">View updates →</button></div>';
      $("nvaMore").onclick=reset;
      $("nvaView").onclick=function(){ afterWrite(res); };
      pending=[];
      setTimeout(function(){ if(state==="done") orb(); },1400);
    }catch(e){ orb(); state="review"; say("⚠️ "+e.message); renderActs(); }
  }

  // route the user to where the change is visible (fresh load shows it)
  function afterWrite(res){
    var ops=res.filter(function(x){return x.ok;}).map(function(x){return x.op;});
    var want = ops.some(function(o){return o.indexOf("deal")>=0;}) ? "ledger"
             : ops.some(function(o){return o.indexOf("note")>=0;}) ? "notes"
             : ops.some(function(o){return o.indexOf("task")>=0;}) ? "tasks" : PAGE;
    if(want===PAGE) location.reload(); else location.href=NAV[want];
  }

  // ---------- voice ----------
  var _rec=null,_recOn=false;
  function mic(){
    var SR=window.SpeechRecognition||window.webkitSpeechRecognition;
    if(!SR){ alert("Voice needs Chrome over HTTPS."); return; }
    if(_recOn){ try{_rec.stop();}catch(e){} return; }
    _rec=new SR(); _rec.lang="en-US"; _rec.interimResults=true; _rec.continuous=true;
    var base=ta.value.trim();
    _rec.onstart=function(){ _recOn=true; $("nvaMic").classList.add("rec"); if(state==="idle")orb("listen"); };
    _rec.onend  =function(){ _recOn=false; $("nvaMic").classList.remove("rec"); if(state==="idle")orb(); };
    _rec.onerror=function(){ _recOn=false; $("nvaMic").classList.remove("rec"); if(state==="idle")orb(); };
    _rec.onresult=function(e){ var t=""; for(var i=0;i<e.results.length;i++) t+=e.results[i][0].transcript; ta.value=(base?base+" ":"")+t; };
    try{_rec.start();}catch(e){}
  }

  // ---------- wire ----------
  $("nvaLaunch").onclick=open;
  $("nvaX").onclick=close;
  scrim.addEventListener("click",function(e){ if(e.target===scrim) close(); });
  $("nvaSend").onclick=function(){ send(); };
  $("nvaMic").onclick=mic;
  ta.addEventListener("keydown",function(e){ if(e.key==="Enter"&&!e.shiftKey){ e.preventDefault(); send(); } });
  ta.addEventListener("input",function(){ this.style.height="auto"; this.style.height=Math.min(this.scrollHeight,130)+"px"; });
  bodyEl.addEventListener("click",function(e){ var c=e.target.closest(".nva-chip"); if(c){ ta.value=c.getAttribute("data-full"); send(); } });
  document.addEventListener("keydown",function(e){
    if((e.metaKey||e.ctrlKey)&&(e.key==="k"||e.key==="K")){ e.preventDefault(); scrim.classList.contains("show")?close():open(); }
    else if(e.key==="Escape"&&scrim.classList.contains("show")) close();
  });
  // ---------- account: identity, sign out, password management ----------
  var amenu=$("nvaAmenu"), acctScrim=$("nvaAcctScrim");
  function renderAmenu(){
    amenu.innerHTML='<div class="who"><b>'+esc(ME.name)+'</b><span>'+esc(ME.role||"owner")+'</span></div>'
      +'<button class="mi" id="miPw">Change my password</button>'
      +(ME.id==="edgar"?'<button class="mi" id="miTeam">Team &amp; passwords</button>':'')
      +'<button class="mi danger" id="miOut">Sign out</button>';
    $("miPw").onclick=function(){ acctMenu(false); openAcct(false); };
    if($("miTeam")) $("miTeam").onclick=function(){ acctMenu(false); openAcct(true); };
    $("miOut").onclick=function(){ location.href="/nova-admins/logout"; };
  }
  function acctMenu(show){ if(show===undefined) show=!amenu.classList.contains("show"); if(show)renderAmenu(); amenu.classList.toggle("show",show); }
  function closeAcct(){ acctScrim.classList.remove("show"); }
  function savePw(uid,pw,pw2,msgEl){
    if((pw||"").length<6){ msgEl.style.color="var(--c-red)"; msgEl.textContent="Too short — 6+ characters."; return; }
    if(pw2!==undefined && pw!==pw2){ msgEl.style.color="var(--c-red)"; msgEl.textContent="Passwords don't match."; return; }
    fetch("/nova-admins/set-password",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({user:uid,password:pw})})
      .then(function(x){return x.json();}).then(function(o){
        if(o.ok){ msgEl.style.color="var(--c-green)"; msgEl.textContent="Saved ✓"; }
        else { msgEl.style.color="var(--c-red)"; msgEl.textContent=o.error||"Failed."; }
      }).catch(function(){ msgEl.style.color="var(--c-red)"; msgEl.textContent="Network error."; });
  }
  window.__novaSetPw=function(uid){ var el=document.getElementById("tp_"+uid); if(!el)return; savePw(uid, el.value, undefined, document.getElementById("teamMsg")); el.value=""; };
  function renderTeam(){
    fetch("/nova-admins/users").then(function(x){return x.json();}).then(function(r){
      var others=(r.users||[]).filter(function(u){return u.id!==ME.id;});
      $("teamWrap").innerHTML='<div class="nva-team"><div class="nva-kick" style="text-align:left;margin-bottom:10px">Set a teammate\'s password</div>'
        +others.map(function(u){ return '<div class="row"><span class="av" style="background:'+(UCOLOR[u.id]||"#3a8eef")+'">'+esc(u.name[0])+'</span>'
          +'<input type="password" id="tp_'+u.id+'" placeholder="'+(u.hasPass?"Reset "+esc(u.name)+"\'s password":"Set "+esc(u.name)+"\'s password")+'">'
          +'<button class="nva-btn" style="padding:8px 12px" onclick="window.__novaSetPw(\''+u.id+'\')">Set</button></div>'; }).join("")
        +'<div class="nva-msg" id="teamMsg"></div></div>';
    }).catch(function(){});
  }
  function openAcct(team){
    acctScrim.classList.add("show");
    var p=$("nvaAcctPanel");
    p.innerHTML='<button class="nva-x" id="acctX">✕</button><div class="nva-kick">Account</div>'
      +'<div class="nva-say" style="margin-bottom:6px">Signed in as '+esc(ME.name)+'</div>'
      +'<div class="nva-acctf"><label>New password</label><input type="password" id="pwNew" placeholder="At least 6 characters" autocomplete="new-password">'
      +'<label>Confirm</label><input type="password" id="pwNew2" placeholder="Repeat it"></div>'
      +'<div class="nva-msg" id="pwMsg"></div>'
      +'<div class="nva-actions"><button class="nva-btn" id="pwSave">Save password</button></div>'
      +'<div id="teamWrap"></div>';
    $("acctX").onclick=closeAcct;
    $("pwSave").onclick=function(){ savePw(ME.id, $("pwNew").value, $("pwNew2").value, $("pwMsg")); };
    if(team && ME.id==="edgar") renderTeam();
  }
  $("nvaAcct").onclick=function(e){ e.stopPropagation(); acctMenu(); };
  acctScrim.addEventListener("click",function(e){ if(e.target===acctScrim) closeAcct(); });
  document.addEventListener("click",function(e){ if(!e.target.closest("#nvaAmenu")&&!e.target.closest("#nvaAcct")) amenu.classList.remove("show"); });

  // pause the orb's animation while the tab is in the background (saves battery)
  function syncPaused(){ root.classList.toggle("paused", document.hidden); }
  document.addEventListener("visibilitychange", syncPaused); syncPaused();
})();
