"""HTML report: data checks + what changed since the last build."""
from __future__ import annotations

import html
from collections import Counter, defaultdict
from pathlib import Path

esc = html.escape


def _val(v):
    if isinstance(v, list):
        return ", ".join(map(str, v)) or "—"
    if v is None or v == "":
        return "—"
    return str(v)


def build_report(findings, changes: dict | None, meta: dict, n_courses: int, built_at: str, export_name: str) -> str:
    sev = Counter(f.severity for f in findings)
    by_rule = defaultdict(list)
    for f in findings:
        by_rule[(f.severity, f.rule)].append(f)

    rule_blocks = []
    for (s, rule), items in by_rule.items():
        rows = "".join(f"<tr><td class='c'>{esc(f.code)}</td><td>{esc(f.message)}</td></tr>" for f in items)
        rule_blocks.append(
            f"<details class='{s}' {'open' if s == 'error' else ''}><summary><span class='pill {s}'>{s}</span>"
            f"<b>{esc(rule)}</b><span class='n'>{len(items)}</span></summary>"
            f"<table><thead><tr><th>Course</th><th>Detail</th></tr></thead><tbody>{rows}</tbody></table></details>"
        )

    if changes is None:
        change_html = "<p class='muted'>First build: no previous snapshot to compare against. The next build will list every added, removed, or edited course here. That list is your addendum draft.</p>"
    else:
        parts = []
        if changes["added"]:
            parts.append("<h3>Added</h3><ul>" + "".join(f"<li><b>{esc(c['code'])}</b> {esc(c['title'])}</li>" for c in changes["added"]) + "</ul>")
        if changes["removed"]:
            parts.append("<h3>Removed</h3><ul>" + "".join(f"<li><b>{esc(c['code'])}</b> {esc(c['title'])}</li>" for c in changes["removed"]) + "</ul>")
        if changes["changed"]:
            items = []
            for ch in changes["changed"]:
                rows = "".join(f"<tr><td>{esc(f)}</td><td class='old'>{esc(_val(o))}</td><td class='new'>{esc(_val(n))}</td></tr>" for f, o, n in ch["fields"])
                items.append(f"<details open><summary><b>{esc(ch['code'])}</b> {esc(ch['title'])}</summary><table><thead><tr><th>Field</th><th>Was</th><th>Now</th></tr></thead><tbody>{rows}</tbody></table></details>")
            parts.append("<h3>Edited</h3>" + "".join(items))
        change_html = "".join(parts) or "<p class='muted'>No course changes since the last build.</p>"
        n = len(changes["added"]) + len(changes["removed"]) + len(changes["changed"])
        change_html = f"<p class='lead'><b>{n}</b> course{'s' if n != 1 else ''} changed since the last build.</p>" + change_html

    prod = meta.get("product", {})
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Catalog build report · {esc(built_at)}</title>
<style>
body{{font:15px/1.5 Lato,system-ui,sans-serif;color:#1b1b1d;background:#f6f5f2;margin:0}}
header{{background:#1b1b1d;color:#fff;border-top:8px solid #f9a719;padding:28px 32px}}
header h1{{font:700 28px Poppins,system-ui,sans-serif;margin:0 0 4px}} header p{{margin:0;color:#cfcdc7}}
main{{max-width:1080px;margin:0 auto;padding:24px 32px 60px}}
.cards{{display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin:0 0 28px}}
.card{{background:#fff;border:1px solid #e2dfd8;border-radius:8px;padding:14px 16px}}
.card b{{display:block;font:700 28px Poppins,system-ui,sans-serif}} .card span{{font:600 12px Poppins,system-ui;letter-spacing:.08em;text-transform:uppercase;color:#55565a}}
.card.error b{{color:#b42318}} .card.warning b{{color:#8a5a00}}
h2{{font:600 20px Poppins,system-ui,sans-serif;border-bottom:3px solid #f9a719;padding-bottom:6px;margin:32px 0 14px}}
details{{background:#fff;border:1px solid #e2dfd8;border-radius:8px;margin:0 0 8px;padding:0}}
summary{{cursor:pointer;padding:10px 14px;display:flex;gap:10px;align-items:center}}
summary .n{{margin-left:auto;font:600 13px Poppins,system-ui;color:#55565a}}
.pill{{font:700 10px Poppins,system-ui;letter-spacing:.08em;text-transform:uppercase;padding:2px 7px;border-radius:3px}}
.pill.error{{background:#fde7e5;color:#b42318}} .pill.warning{{background:#fdf0d5;color:#8a5a00}} .pill.info{{background:#eceae4;color:#55565a}}
table{{width:100%;border-collapse:collapse;font-size:14px}} th,td{{text-align:left;padding:6px 14px;border-top:1px solid #eeebe4;vertical-align:top}}
th{{font:600 11px Poppins,system-ui;letter-spacing:.08em;text-transform:uppercase;color:#55565a}}
td.c{{white-space:nowrap;font-weight:700}} td.old{{color:#b42318;text-decoration:line-through}} td.new{{color:#146c2e}}
.muted{{color:#55565a}} .lead{{font-size:17px}}
</style></head><body>
<header><h1>Catalog build report</h1><p>{esc(built_at)} · {esc(export_name)} · {esc(prod.get('NAME',''))} {esc(prod.get('VERSION',''))}</p></header>
<main>
<div class="cards">
 <div class="card"><b>{n_courses:,}</b><span>Courses built</span></div>
 <div class="card error"><b>{sev.get('error',0)}</b><span>Errors</span></div>
 <div class="card warning"><b>{sev.get('warning',0)}</b><span>Warnings</span></div>
 <div class="card"><b>{sev.get('info',0)}</b><span>Notes (auto-fixed)</span></div>
</div>
<h2>What changed since last build</h2>
{change_html}
<h2>Data checks</h2>
<p class="muted">Errors should be fixed in FileMaker before publishing. Warnings need a human decision. Notes were cleaned up automatically in the output, but are worth fixing at the source.</p>
{''.join(rule_blocks)}
</main></body></html>"""


def write_report(path: Path, **kw) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(build_report(**kw), encoding="utf-8")
    return path
