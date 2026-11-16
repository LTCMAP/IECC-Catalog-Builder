"""Single-file, searchable, accessible web version of the course descriptions."""
from __future__ import annotations

import base64
import json
from pathlib import Path

from .model import CAMPUSES
from .outputs import ASSETS, subject_name

FONTS = [("Jost", 400, "jost-latin-400-normal"), ("Jost", 500, "jost-latin-500-normal"), ("Jost", 600, "jost-latin-600-normal"),
         ("Garamond", 400, "eb-garamond-latin-400-normal"), ("Garamond", 600, "eb-garamond-latin-600-normal")]


def _font_faces() -> str:
    out = []
    for fam, w, f in FONTS:
        b = base64.b64encode((ASSETS / "fonts" / f"{f}.woff2").read_bytes()).decode()
        out.append(f"@font-face{{font-family:'{fam}';font-weight:{w};font-display:swap;src:url(data:font/woff2;base64,{b}) format('woff2')}}")
    return "\n".join(out)


def build_web_html(courses, prefixes, built_at: str) -> str:
    data = [
        {
            "c": c.code, "p": c.prefix, "t": c.title, "cr": c.credits_label, "v": c.variable, "d": c.description,
            "pre": c.prerequisite, "co": c.corequisite, "dl": c.delivery, "r": c.repeatable, "camp": c.campuses,
            "iai": c.iai, "cls": c.classification,
        }
        for c in courses
    ]
    subjects = {c.prefix: subject_name(c.prefix, prefixes) for c in courses}
    return TEMPLATE.replace("/*FONTS*/", _font_faces()) \
        .replace("__DATA__", json.dumps(data, ensure_ascii=False, separators=(",", ":"))) \
        .replace("__SUBJECTS__", json.dumps(subjects, ensure_ascii=False)) \
        .replace("__BUILT__", built_at)


def write_web(courses, prefixes, out_dir: Path, built_at: str) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    p = out_dir / "course-descriptions.html"
    p.write_text(build_web_html(courses, prefixes, built_at), encoding="utf-8")
    return p


TEMPLATE = r"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Course Descriptions | IECC Academic Catalog</title>
<style>
/*FONTS*/
:root{--ink:#1d2124;--muted:#4f5759;--rule:#d5dcdb;--gold:#027789;--gold-ink:#01596a;--cream:#e3f0f2;--bg:#f3f6f6;--fcc:#f3d03e;--ltc:#154734;--occ:#283345;--wvc:#ce202f}
*{box-sizing:border-box}
body{margin:0;font:17px/1.55 Garamond,Georgia,serif;color:var(--ink);background:var(--bg)}
a{color:inherit}
.skip{position:absolute;left:-999px}.skip:focus{left:12px;top:12px;background:#fff;padding:8px 12px;z-index:9}
header.hero{background:var(--gold);color:#fff;padding:40px 24px 28px;border-top:8px solid var(--ink)}
.wrap{max-width:1180px;margin:0 auto}
.kicker{font:500 13px Jost,sans-serif;letter-spacing:.2em;text-transform:uppercase;color:#fff;opacity:.85;margin:0 0 6px}
h1{font:500 clamp(30px,5vw,48px)/1.05 Jost,sans-serif;text-transform:uppercase;letter-spacing:.03em;margin:0 0 10px}
.hero p{margin:0;color:#e9f4f6;max-width:640px}
.controls{position:sticky;top:0;z-index:5;background:#fff;border-bottom:1px solid var(--rule);box-shadow:0 2px 10px rgba(0,0,0,.04)}
.controls .wrap{display:grid;grid-template-columns:2fr 1.4fr 1fr auto;gap:12px;padding:14px 24px;align-items:end}
label.f,legend.f{display:block;padding:0;font:600 12px Jost,sans-serif;letter-spacing:.06em;text-transform:uppercase;color:var(--muted);margin-bottom:4px}
input[type=search],select{width:100%;font:inherit;padding:10px 12px;border:1.5px solid #c9c6be;border-radius:6px;background:#fff}
input[type=search]:focus,select:focus,button:focus,.chk input:focus{outline:3px solid var(--gold);outline-offset:1px}
fieldset{border:0;padding:0;margin:0}
.camps{display:flex;gap:6px;flex-wrap:wrap}
.chk{display:inline-flex;align-items:center;gap:5px;font:600 13px Jost,sans-serif;border:1.5px solid #c9c6be;border-radius:6px;padding:8px 10px;cursor:pointer;background:#fff}
.chk:has(input:checked){background:var(--gold);border-color:var(--gold);color:#fff}
.chk input{accent-color:var(--ink)}
button.reset{font:600 13px Jost,sans-serif;padding:10px 14px;border-radius:6px;border:1.5px solid var(--ink);background:#fff;cursor:pointer}
.status{font:500 14px Jost,sans-serif;color:var(--muted);padding:16px 24px 0}
main .wrap{padding:0 24px 60px}
.layout{display:grid;grid-template-columns:220px 1fr;gap:32px}
nav.subjects{position:sticky;top:96px;align-self:start;max-height:calc(100vh - 120px);overflow:auto;font-size:14px;padding:18px 0}
nav.subjects h2{font:600 12px Jost,sans-serif;letter-spacing:.1em;text-transform:uppercase;color:var(--muted);margin:0 0 8px}
nav.subjects ul{list-style:none;margin:0;padding:0}
nav.subjects a{display:flex;gap:8px;text-decoration:none;padding:3px 6px;border-radius:4px}
nav.subjects a:hover{background:#fff}
nav.subjects b{font:600 12px Jost,sans-serif;min-width:34px}
section.subject{margin-top:28px}
.sh{display:flex;align-items:center;gap:10px;border-bottom:3px solid var(--gold);padding-bottom:8px;margin-bottom:12px}
.sh h2{font:500 21px/1.2 Jost,sans-serif;text-transform:uppercase;letter-spacing:.04em;margin:0}
.chip{background:var(--gold);color:#fff;font:700 14px Jost,sans-serif;letter-spacing:.08em;padding:4px 8px;border-radius:3px}
.sh .n{margin-left:auto;font:500 13px Jost,sans-serif;color:var(--muted)}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(330px,1fr));gap:14px}
article.course{background:#fff;border:1px solid var(--rule);border-radius:8px;padding:16px 18px 14px;display:flex;flex-direction:column}
.top{display:flex;justify-content:space-between;align-items:baseline;gap:8px}
.code{font:700 14px Jost,sans-serif;letter-spacing:.05em}
.cr{font:500 12px Jost,sans-serif;letter-spacing:.08em;text-transform:uppercase;background:var(--gold);color:#fff;padding:3px 8px;border-radius:3px;white-space:nowrap}
.cr.var{background:#fff;color:var(--ink);box-shadow:inset 0 0 0 1.5px var(--ink)}
article h3{font:600 19px/1.3 Garamond,Georgia,serif;margin:4px 0 8px}
.meta{display:flex;flex-wrap:wrap;gap:6px;align-items:center;margin-bottom:10px}
.camp{display:inline-flex;gap:3px;margin-right:4px}
.camp i{font:normal 600 11px/18px Jost,sans-serif;width:18px;height:18px;text-align:center;border:1.5px solid #cfccc4;border-radius:3px}
.camp i.on{border:0;color:#fff}.camp i.FCC{background:var(--fcc);color:#000}.camp i.LTC{background:var(--ltc)}.camp i.OCC{background:var(--occ)}.camp i.WVC{background:var(--wvc)}
.tag{font:600 11px Jost,sans-serif;letter-spacing:.05em;text-transform:uppercase;color:var(--muted);border:1px solid var(--rule);border-radius:3px;padding:2px 6px}
.tag.iai{color:var(--gold-ink);background:var(--cream);border-color:#f1d49e}
.desc{margin:0;font-size:17px}
.req{margin:10px 0 0;font-size:14px;background:var(--cream);border-left:3px solid var(--gold);padding:6px 10px}
.req b{font:600 11px Jost,sans-serif;letter-spacing:.08em;text-transform:uppercase;margin-right:6px}
mark{background:#fbe9a3;padding:0 1px}
.sr{position:absolute;width:1px;height:1px;overflow:hidden;clip:rect(0 0 0 0)}
footer{color:var(--muted);font-size:13px;text-align:center;padding:24px}
@media (max-width:860px){.controls .wrap{grid-template-columns:1fr 1fr}.layout{grid-template-columns:1fr}nav.subjects{display:none}}
@media (prefers-reduced-motion:no-preference){html{scroll-behavior:smooth}}
</style></head>
<body>
<a class="skip" href="#results">Skip to course list</a>
<header class="hero"><div class="wrap">
  <p class="kicker">IECC Academic Catalog</p>
  <h1>Course Descriptions</h1>
  <p>Search every credit course offered at Frontier, Lincoln Trail, Olney Central, and Wabash Valley. Filter by subject, college, or transfer status.</p>
</div></header>

<div class="controls" role="search"><div class="wrap">
  <div><label class="f" for="q">Search</label><input id="q" type="search" placeholder="Course code, title, or keyword (e.g. ACC 1101, welding, IAI)"></div>
  <div><label class="f" for="subj">Subject</label><select id="subj"><option value="">All subjects</option></select></div>
  <fieldset><legend class="f">Offered at</legend><div class="camps" id="camps"></div></fieldset>
  <div><label class="chk" for="iai"><input type="checkbox" id="iai"> IAI only</label></div>
</div></div>

<p class="status wrap" id="status" aria-live="polite"></p>
<main id="results" tabindex="-1"><div class="wrap"><div class="layout">
  <nav class="subjects" aria-label="Subjects"><h2>Subjects</h2><ul id="nav"></ul></nav>
  <div id="list"></div>
</div></div></main>
<footer>Generated from the IECC course database · __BUILT__</footer>

<script>
const DATA=__DATA__, SUBJ=__SUBJECTS__;
const CAMP=[["FCC","F","Frontier"],["LTC","L","Lincoln Trail"],["OCC","O","Olney Central"],["WVC","W","Wabash Valley"]];
const $=s=>document.querySelector(s), esc=s=>(s??"").replace(/[&<>"]/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[c]));
const subjSel=$("#subj"); Object.entries(SUBJ).forEach(([p,n])=>subjSel.add(new Option(`${p} — ${n}`,p)));
$("#camps").innerHTML=CAMP.map(([c,l,n])=>`<label class="chk" title="${n}"><input type="checkbox" value="${c}"> ${c}</label>`).join("");
const state={q:"",s:"",camps:[],iai:false};
function hl(text,terms){let t=esc(text);for(const w of terms){if(w.length<2)continue;t=t.replace(new RegExp("("+w.replace(/[.*+?^${}()|[\]\\]/g,"\\$&")+")","gi"),"<mark>$1</mark>")}return t}
function card(c,terms){
  const camp=CAMP.map(([k,l,n])=>c.camp.includes(k)?`<i class="on ${k}" title="${n}">${l}</i>`:`<i aria-hidden="true"></i>`).join("");
  const off=CAMP.filter(([k])=>c.camp.includes(k)).map(x=>x[2]).join(", ");
  const tags=[c.dl&&`<span class="tag">${esc(c.dl)}</span>`,c.r&&`<span class="tag">Repeatable ${c.r}×</span>`,...c.iai.map(i=>`<span class="tag iai">IAI ${esc(i)}</span>`)].filter(Boolean).join("");
  return `<article class="course" aria-labelledby="t-${c.c.replace(' ','')}">
   <div class="top"><span class="code">${hl(c.c,terms)}</span><span class="cr${c.v?" var":""}">${c.v?"Up to ":""}${c.cr} cr</span></div>
   <h3 id="t-${c.c.replace(' ','')}">${hl(c.t,terms)}</h3>
   <div class="meta"><span class="camp" role="img" aria-label="Offered at ${off}">${camp}</span>${tags}</div>
   <p class="desc">${hl(c.d,terms)}</p>
   ${c.pre?`<p class="req"><b>Prerequisite</b>${hl(c.pre,terms)}</p>`:""}${c.co?`<p class="req"><b>Corequisite</b>${hl(c.co,terms)}</p>`:""}
  </article>`}
function render(){
  const terms=state.q.trim().split(/\s+/).filter(Boolean), qn=state.q.trim().toLowerCase().replace(/\s+/g," ");
  const rows=DATA.filter(c=>{
    if(state.s&&c.p!==state.s)return false;
    if(state.camps.length&&!state.camps.every(x=>c.camp.includes(x)))return false;
    if(state.iai&&!c.iai.length)return false;
    if(!qn)return true;
    const hay=(c.c+" "+c.c.replace(" ","")+" "+c.t+" "+c.d+" "+(c.pre||"")+" "+c.iai.join(" ")+" "+SUBJ[c.p]).toLowerCase();
    return terms.every(t=>hay.includes(t.toLowerCase()));
  });
  const groups={};rows.forEach(c=>(groups[c.p]??=[]).push(c));
  $("#list").innerHTML=Object.entries(groups).map(([p,cs])=>`<section class="subject" id="s-${p}" aria-labelledby="h-${p}">
     <div class="sh"><span class="chip">${p}</span><h2 id="h-${p}">${esc(SUBJ[p])}</h2><span class="n">${cs.length} course${cs.length>1?"s":""}</span></div>
     <div class="grid">${cs.map(c=>card(c,terms)).join("")}</div></section>`).join("")||`<p>No courses match. Try a different search or clear the filters.</p>`;
  $("#nav").innerHTML=Object.entries(groups).map(([p,cs])=>`<li><a href="#s-${p}"><b>${p}</b>${esc(SUBJ[p])}</a></li>`).join("");
  $("#status").textContent=`Showing ${rows.length.toLocaleString()} of ${DATA.length.toLocaleString()} courses`;
}
let t;$("#q").addEventListener("input",e=>{clearTimeout(t);t=setTimeout(()=>{state.q=e.target.value;render()},120)});
subjSel.addEventListener("change",e=>{state.s=e.target.value;render()});
$("#camps").addEventListener("change",()=>{state.camps=[...document.querySelectorAll("#camps input:checked")].map(i=>i.value);render()});
$("#iai").addEventListener("change",e=>{state.iai=e.target.checked;render()});
render();
</script></body></html>"""
