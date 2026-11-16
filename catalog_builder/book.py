"""Assemble the full catalog (cover → contents → sections → programs → courses → back) from
content/ (editable text, calendar, programs) + the FileMaker course export."""
from __future__ import annotations

import csv
import html
import json
import re
from collections import OrderedDict
from pathlib import Path

from .model import CAMPUSES, Course
from .outputs import ASSETS, course_html, group_by_subject, subject_name

esc = html.escape
COLLEGE_COLOR = {"FCC": "var(--fcc)", "LTC": "var(--ltc)", "OCC": "var(--occ)", "WVC": "var(--wvc)"}
STRIPE_COLORS = ["#ce202f", "#283345", "#154734", "#f3d03e", "#027789"]  # brand-book cover order


def slug(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")


# ------------------------------------------------------------------ brand stripes
def stripes_diag(w=1000, h=600, thick=26, gap=14, rise=0.42) -> str:
    """Five parallel diagonal bands, bottom-left to top-right, like the brand book cover."""
    lines = []
    for i, col in enumerate(STRIPE_COLORS):
        off = i * (thick + gap)
        y0 = h - 40 + off - len(STRIPE_COLORS) * (thick + gap) / 2
        lines.append(f'<line x1="-20" y1="{y0 + 140:.0f}" x2="{w + 20}" y2="{y0 - w * rise + 140:.0f}" stroke="{col}" stroke-width="{thick}"/>')
    return f'<svg viewBox="0 0 {w} {h}" preserveAspectRatio="none" aria-hidden="true">{"".join(lines)}</svg>'


def stripes_vert(w=100, h=500) -> str:
    bars = "".join(f'<rect x="{i * 20}" y="0" width="9" height="{h}" fill="{c}"/>' for i, c in enumerate(STRIPE_COLORS))
    return f'<svg viewBox="0 0 {w} {h}" preserveAspectRatio="none" aria-hidden="true">{bars}</svg>'


# ------------------------------------------------------------------ mini markdown
def _inline(s: str) -> str:
    s = esc(s)
    s = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", s)
    s = re.sub(r"(?<!\*)\*(?!\s)(.+?)(?<!\s)\*(?!\*)", r"<em>\1</em>", s)
    return s


def md_to_html(text: str, id_prefix: str = "") -> tuple[str, list[tuple[str, str]], int, str | None]:
    """Returns (html, [(heading, anchor)], todo_count, page_title). Supports #, ##, ###, -, 1., |tables|, >, TODO:."""
    text = re.sub(r"<!--.*?-->", "", text, flags=re.S)
    out, heads, todos, title = [], [], 0, None
    lines = text.splitlines()
    i = 0
    para: list[str] = []

    def flush():
        if para:
            out.append(f"<p>{_inline(' '.join(para))}</p>")
            para.clear()

    while i < len(lines):
        ln = lines[i].rstrip()
        if not ln.strip():
            flush(); i += 1; continue
        if ln.startswith("# "):
            flush(); title = ln[2:].strip(); i += 1; continue
        m = re.match(r"(#{2,3}) (.+)", ln)
        if m:
            flush()
            lvl, t = len(m.group(1)), m.group(2).strip()
            aid = f"{id_prefix}{slug(t)}"
            if lvl == 2:
                heads.append((t, aid))
            out.append(f'<h{lvl} id="{aid}">{_inline(t)}</h{lvl}>'); i += 1; continue
        if ln.startswith("TODO:"):
            flush(); todos += 1
            out.append(f'<div class="todo">{_inline(ln[5:].strip())}</div>'); i += 1; continue
        if ln.startswith(">"):
            flush(); buf = []
            while i < len(lines) and lines[i].startswith(">"):
                buf.append(lines[i][1:].strip()); i += 1
            out.append(f"<blockquote>{_inline(' '.join(buf))}</blockquote>"); continue
        if re.match(r"\s*[-•] ", ln) or re.match(r"\s*\d+\. ", ln):
            flush()
            ordered = bool(re.match(r"\s*\d+\. ", ln))
            items = []
            while i < len(lines) and (re.match(r"\s*[-•] ", lines[i]) or re.match(r"\s*\d+\. ", lines[i])):
                items.append(re.sub(r"^\s*([-•]|\d+\.) ", "", lines[i])); i += 1
            tag = "ol" if ordered else "ul"
            start = re.match(r"\s*(\d+)\.", ln)
            attr = f' start="{start.group(1)}"' if ordered and start and start.group(1) != "1" else ""
            out.append(f"<{tag}{attr}>" + "".join(f"<li>{_inline(x)}</li>" for x in items) + f"</{tag}>"); continue
        if ln.startswith("|"):
            flush(); rows = []
            while i < len(lines) and lines[i].startswith("|"):
                cells = [c.strip() for c in lines[i].strip().strip("|").split("|")]
                if not all(re.fullmatch(r":?-{2,}:?", c) for c in cells):
                    rows.append(cells)
                i += 1
            if rows:
                todos += sum(1 for r in rows[1:] for c in r if c.startswith("TODO"))
                th = "".join(f"<th>{_inline(c)}</th>" for c in rows[0])
                body = "".join("<tr>" + "".join(
                    f'<td>{"<span class=todo-inline>" if c.startswith("TODO") else ""}{_inline(c.replace("TODO:", "").replace("TODO", "—").strip())}</td>'
                    for c in r) + "</tr>" for r in rows[1:])
                out.append(f"<table><thead><tr>{th}</tr></thead><tbody>{body}</tbody></table>")
            continue
        para.append(ln.strip()); i += 1
    flush()
    return "\n".join(out), heads, todos, title


# ------------------------------------------------------------------ programs
class ProgramIssues(list):
    pass


def render_program(p: dict, by_code: dict[str, Course], issues: list, registry: dict | None = None) -> tuple[str, float]:
    pid = f"prog-{slug(p['code'] + ' ' + p['title'])}"
    marks_used = set()

    def course_cell(code: str, gened=False, diversity=False):
        c = by_code.get(code)
        sup = ("¹" if gened else "") + ("*" if diversity else "")
        if sup:
            marks_used.add("g" if gened else ""); marks_used.add("d" if diversity else "")
        if not c:
            issues.append(("warning", "Program uses course not in FileMaker", code, f"{p['title']} ({p['code']}) lists {code}, which isn't in the export."))
            return f'<td class="c">{esc(code)}</td><td>{esc(code)} <span class="missing">not in FileMaker</span></td>', 0.0, False
        t = f'{esc(c.title)}{f"<sup>{sup}</sup>" if sup else ""}'
        return f'<td class="c">{esc(code)}</td><td>{t}</td>', c.credits, c.variable

    def item_row(it) -> tuple[str, float]:
        if "course" in it:
            cells, cr, var = course_cell(it["course"], it.get("gened"), it.get("diversity"))
            return f"<tr>{cells}<td class='cr'>{'V' if var else ''}{cr:g}</td></tr>", cr
        if "any" in it:
            codes = it["any"]
            parts, crs, var = [], [], False
            for k in codes:
                c = by_code.get(k)
                if not c:
                    issues.append(("warning", "Program uses course not in FileMaker", k, f"{p['title']} ({p['code']}) lists {k}, which isn't in the export."))
                sup = ("¹" if it.get("gened") else "") + ("*" if it.get("diversity") else "")
                title = esc(c.title) if c else '<span class="missing">not in FileMaker</span>'
                parts.append(f"<b>{esc(k)}</b> {title}{f'<sup>{sup}</sup>' if sup else ''}")
                if c:
                    crs.append(c.credits); var = var or c.variable
            if len(set(crs)) > 1:
                issues.append(("warning", "OR choices with different credits", " / ".join(codes), f"{p['title']}: alternatives carry {', '.join(f'{x:g}' for x in crs)} credits."))
            cr = max(crs) if crs else 0
            if it.get("gened"): marks_used.add("g")
            if it.get("diversity"): marks_used.add("d")
            joined = ' <span class="or">OR</span> '.join(parts)
            return f"<tr><td class='c'>Choose</td><td>{joined}</td><td class='cr'>{'V' if var else ''}{cr:g}</td></tr>", cr
        if "label" in it:
            return f"<tr class='slot'><td class='c'></td><td>{esc(it['label'])}</td><td class='cr'>{it.get('credits', 0):g}</td></tr>", float(it.get("credits", 0))
        return "", 0.0

    terms_html, total = [], 0.0
    for t in p.get("terms", []):
        rows, sub = [], 0.0
        for it in t["items"]:
            r, cr = item_row(it); rows.append(r); sub += cr
        total += sub
        terms_html.append(f'<div class="term"><div class="th"><span>{esc(t["name"])}</span><span>{sub:g} credit hours</span></div><table>{"".join(rows)}</table></div>')
    if p.get("stated_total") is not None and abs(p["stated_total"] - total) > 0.01:
        issues.append(("warning", "Program total differs", p["code"], f"{p['title']}: courses add up to {total:g} hours from FileMaker credits; the program says {p['stated_total']:g}."))

    opts = ""
    if p.get("option_groups"):
        g = p["option_groups"]
        grps = []
        for grp in g["groups"]:
            rows = []
            for it in grp["items"]:
                r, _ = item_row(it)
                rows.append(r.replace("<td class='c'>Choose</td>", "<td class='c'>Choose</td>"))
            grps.append(f'<div class="grp"><h4>{esc(grp["name"])}</h4><table>{"".join(rows)}</table></div>')
        opts = f'<div class="options"><h3>{esc(g["title"])}</h3><div class="groups">{"".join(grps)}</div></div>'

    notes = []
    if "g" in marks_used:
        gh = " ({} hours)".format(p["gened_hours"]) if p.get("gened_hours") else ""
        notes.append("<sup>¹</sup> General education" + gh)
    if "d" in marks_used:
        notes.append("* Satisfies the IECC human diversity requirement")
    notes.append("V = variable credit")
    camp = "".join(
        f'<i class="on {c}">{l}</i>' if c in p.get("campuses", []) else '<i aria-hidden="true"></i>' for c, l, _ in CAMPUSES
    )
    offered = ", ".join(n for c, _, n in CAMPUSES if c in p.get("campuses", []))
    return (f'<section class="program" id="{pid}">'
            f'<div class="kicker">{esc(p["award"])}{(" · " + esc((registry or {}).get(p["code"].split()[-1], {}).get("meta_major", ""))) if (registry or {}).get(p["code"].split()[-1], {}).get("meta_major") else ""}</div><h2>{esc(p["title"])}</h2>'
            f'<div class="meta"><span class="code">{esc(p["code"])}</span><span class="camp" aria-label="Offered at {esc(offered)}">{camp}</span><span>{esc(offered)}</span></div>'
            f'<p class="desc">{esc(p.get("description", ""))}</p>'
            f'<div class="terms">{"".join(terms_html)}</div>'
            f'<div class="total"><span>Total credit hours</span><b>{total:g}</b></div>'
            f'<p class="notes">{" · ".join(notes)}</p>{opts}</section>'), total


# ------------------------------------------------------------------ course section
def courses_html(courses: list[Course], prefixes: dict) -> tuple[str, list[tuple[str, str]]]:
    groups = group_by_subject(courses, prefixes)
    sample = next((c for c in courses if c.iai and c.prerequisite), courses[0])
    legend = "".join(f'<span><span class="camp"><i class="on {c}">{l}</i></span>{n}</span>' for c, l, n in CAMPUSES)
    howto = f"""<section class="howto" id="how-to-read"><h1 class="page-title">How to Read a Course Entry</h1>
<p class="intro">Each listing shows where the course is offered, its credit hours, how it is delivered, and anything you need to complete first. For current schedules and locations, visit iecc.edu/schedules.</p>
<div class="demo"><div class="sample">{course_html(sample)}</div><ol>
<li><b>Code &amp; credits.</b> Subject prefix and number, with credit hours. An outlined badge (“Up to”) means variable credit.</li>
<li><b>Where it’s offered.</b> Each college appears in its own color:<div class="legend">{legend}</div></li>
<li><b>Format.</b> Lecture, Lab, Clinical, or Internship, and how many times the course may be repeated.</li>
<li><b>IAI code.</b> Illinois Articulation Initiative number for courses that transfer to participating Illinois schools.</li>
<li><b>Prerequisite / Corequisite.</b> What you must complete before, or take alongside, this course.</li></ol></div>
<p class="code-demo"><span>LSC</span> <span>1</span><span>1</span><span>01</span></p>
<div class="numbering">
<div class="card"><h3 id="course-prefixes">Prefix</h3><p>Three letters identify the subject. LSC is Life Science.</p></div>
<div class="card"><h3 id="course-numbering">Level</h3><ul><li>0 Below freshman level</li><li>1 First-year</li><li>2 Second-year</li></ul></div>
<div class="card"><h3>Type</h3><ul><li>1 Baccalaureate</li><li>2 Career &amp; Technical</li><li>4 Developmental · 6 Vocational</li><li>7 ABE · 8 ASE · 9 ESL</li></ul></div>
<div class="card"><h3>Sequence</h3><p>Order of the course within its subject.</p></div></div></section>"""
    idx = "".join(f'<li><span class="px">{p}</span><a href="#s-{p}">{esc(subject_name(p, prefixes))}</a></li>' for p in groups)
    index = f'<section class="subject-index" id="subject-index"><h1 class="page-title">Subjects</h1><ol>{idx}</ol></section>'
    subs = []
    for p, cs in groups.items():
        name = subject_name(p, prefixes)
        subs.append(f'<section class="subject" id="s-{p}"><div class="subject-head"><h2 data-running="{p} · {esc(name)}"><span class="chip">{p}</span>{esc(name)}</h2><div class="bar"></div></div>'
                    + "".join(course_html(c) for c in cs) + "</section>")
    listing = f'<main class="listing" id="course-descriptions">{"".join(subs)}</main>'
    return howto + index + listing, [("How to Read a Course Entry", "how-to-read"), ("Subjects", "subject-index"), ("Course Descriptions", "course-descriptions")]


# ------------------------------------------------------------------ calendar
def calendar_html(path: Path) -> tuple[str, int, list[tuple[str, str]]]:
    terms: OrderedDict[str, list] = OrderedDict()
    todos = 0
    with path.open(encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            terms.setdefault(r["term"], []).append(r)
    out, heads = [], []
    for t, rows in terms.items():
        trs = []
        for r in rows:
            if "TODO" in r["event"] or "TODO" in r["days"]:
                todos += 1
                trs.append(f'<tr><td colspan="3"><div class="todo">{esc(r["event"].replace("TODO:", "").strip())}</div></td></tr>')
                continue
            trs.append(f'<tr><td class="m">{esc(r["month"])}</td><td class="d">{esc(r["days"])}</td><td>{esc(r["event"])}</td></tr>')
        aid = f"cal-{slug(t)}"
        heads.append((t, aid))
        out.append(f'<div class="term"><h2 id="{aid}">{esc(t)}</h2><table>{"".join(trs)}</table></div>')
    return f'<div class="calendar">{"".join(out)}</div>', todos, heads


# ------------------------------------------------------------------ assemble
def build_book_html(courses: list[Course], prefixes: dict, content_dir: Path, logo: Path | None = None) -> tuple[str, dict]:
    cat = json.loads((content_dir / "catalog.json").read_text(encoding="utf-8"))
    by_code = {c.code: c for c in courses}
    stats = {"todos": {}, "issues": [], "programs": 0}
    from .policies import load_register, expand, register_issues
    policy_reg = load_register(content_dir)
    stats["issues"].extend(register_issues(policy_reg, cat.get("policies_reviewed", "")))

    def _md(name):
        from .trustees import expand as expand_trustees
        return expand_trustees(expand((content_dir / name).read_text(encoding="utf-8"), content_dir, policy_reg, stats["issues"], name), content_dir)
    programs = [json.loads(f.read_text(encoding="utf-8")) for f in sorted((content_dir / "programs").glob("*.json"))]
    _reg = content_dir / "programs" / "program-registry.csv"
    registry_by_code = {}
    if _reg.exists():
        with _reg.open(encoding="utf-8") as fh:
            registry_by_code = {r["code"]: r for r in csv.DictReader(fh)}

    # ---- cover
    logo_html = f'<img src="{logo.as_uri()}" alt="Illinois Eastern Community Colleges logo">' if logo else ""
    colleges = "".join(f'<div style="border-color:{COLLEGE_COLOR[c["code"]]}">{esc(c["name"])}</div>' for c in cat["colleges"])
    cover = (f'<section class="cover" aria-label="Cover"><div class="brandline">{logo_html}<span>{esc(cat["district"])}</span></div>'
             f'<div class="stripes vert">{stripes_vert()}</div>'
             f'<div class="year">{esc(cat["year"])}</div><h1>ACADEMIC<br>CATALOG</h1>'
             f'<div class="stripes diag">{stripes_diag()}</div><div class="colleges">{colleges}</div></section>')

    # ---- inside cover: contacts
    cards = "".join(
        f'<div class="college" style="border-color:{COLLEGE_COLOR[c["code"]]}"><h3>{esc(c["name"])}</h3>'
        f'<p>{esc(c["address"])}<br>{esc(c["city"])}<br>{esc(c["phone"])} · Toll-free {esc(c["tollfree"])}</p></div>'
        for c in cat["colleges"])
    d = cat["district_office"]
    contacts = (f'<section class="contacts"><h2>Our Colleges</h2><p class="lede">Four colleges, one district, serving southeastern Illinois.</p>'
                f'<div class="grid">{cards}</div><div class="district"><h3>{esc(d["name"])}</h3><p>{esc(d["address"])} · {esc(d["city"])}<br>{esc(d["phone"])} · Toll-free {esc(d["tollfree"])}</p></div>'
                f'<p class="note">For the most up-to-date catalog information, visit {esc(cat["url"])}</p></section>')

    # ---- front matter (single-column prose pages)
    toc_entries = []  # (number, title, anchor, [(sub, anchor)])
    front = []
    for f in cat.get("front_matter", []):
        body, heads, todos, title = md_to_html(_md(f), id_prefix=slug(Path(f).stem) + "-")
        aid = slug(Path(f).stem)
        stats["todos"][f] = todos
        front.append(f'<section class="front" id="{aid}"><h1 class="page-title">{esc(title or aid)}</h1><div class="prose single">{body}</div></section>')
        toc_entries.append(("", title or aid, aid, []))

    # ---- sections
    secs = []
    n = 0
    for s in cat["sections"]:
        n += 1
        num = f"{n:02d}"
        aid = f"sec-{s['id']}"
        content, subs, auto = "", [], ""
        if s["type"] == "calendar":
            content, todos, subs = calendar_html(content_dir / "calendar.csv")
            stats["todos"]["calendar.csv"] = todos
            auto = "Generated from content/calendar.csv"
        elif s["type"] == "md":
            body, subs, todos, _ = md_to_html(_md(s["text"]), id_prefix=f"{s['id']}-")
            stats["todos"][s["text"]] = todos
            content = f'<div class="prose">{body}</div>'
        elif s["type"] == "programs":
            parts = []
            if s.get("text"):
                body, subs, todos, _ = md_to_html(_md(s["text"]), id_prefix=f"{s['id']}-")
                stats["todos"][s["text"]] = todos
                parts.append(f'<div class="prose">{body}</div>')
            group = [p for p in programs if p.get("group") == s.get("program_group")]
            for p in group:
                h, _ = render_program(p, by_code, stats["issues"], registry_by_code)
                parts.append(h); stats["programs"] += 1
                subs.append((f'{p["title"]} ({p["award"]})', f"prog-{slug(p['code'] + ' ' + p['title'])}"))
            if not group:
                parts.append(f'<div class="todo">Add program files to content/programs/ with "group": "{s.get("program_group")}". Course titles and credits fill in from FileMaker.</div>')
                stats["todos"][f"programs:{s.get('program_group')}"] = 1
            content = "".join(parts)
            auto = "Program pages built from content/programs + FileMaker"
        elif s["type"] == "courses":
            content, subs = courses_html(courses, prefixes)
            auto = f"Generated from FileMaker · {len(courses):,} courses"
        sub_list = "".join(f'<li><span>{esc(t)}</span><a href="#{a}"></a></li>' for t, a in subs[:28])
        opener = (f'<section class="opener" id="{aid}"><div class="num">{num}</div><h1>{esc(s["title"])}</h1><div class="bar"></div>'
                  f'<ul>{sub_list}</ul><div class="stripes diag">{stripes_diag(800, 600, 30, 16, 0.55)}</div>'
                  + (f'<div class="auto">{esc(auto)}</div>' if auto else "") + "</section>")
        secs.append(opener + content)
        toc_entries.append((num, s["title"], aid, subs))

    # ---- program index, grouped by meta major (content/programs/program-registry.csv)
    reg_path = content_dir / "programs" / "program-registry.csv"
    if reg_path.exists():
        with reg_path.open(encoding="utf-8") as fh:
            registry = list(csv.DictReader(fh))
        built = {p["code"].split()[-1]: f"prog-{slug(p['code'] + ' ' + p['title'])}" for p in programs}
        MM_ORDER = ["Arts & Social Sciences", "Business & Advanced Technologies", "Education & Public Service",
                    "Health Professions", "Science, Technology, Engineering, & Mathematics", ""]
        groups = OrderedDict((m, []) for m in MM_ORDER)
        for r in registry:
            groups.setdefault(r["meta_major"], []).append(r)
            if r.get("source") == "catalog-2026-27":
                stats["issues"].append(("warning", "Program missing from meta majors site", r["code"], f"{r['title']} is in the 2026–27 catalog but not on my.iecc.edu/metamajors (retired, renamed, or missing?)."))
        type_order = {"Degree": 0, "Transfer": 1, "Certificate": 2}
        blocks = []
        for mm, rows in groups.items():
            if not rows:
                continue
            trs = []
            for r in sorted(rows, key=lambda x: (x["department"] or "~", type_order.get(x["type"], 9), x["title"])):
                camps = r["campuses"].split()
                chips = "".join('<i class="on %s">%s</i>' % (c, l) if c in camps else "<i></i>" for c, l, _ in CAMPUSES)
                pg = f'<a class="pg" href="#{built[r["code"]]}"></a>' if r["code"] in built else '<span class="pg none">—</span>'
                trs.append(f'<tr><td class="t">{esc(r["title"])}</td><td class="d">{esc(r["department"] or "—")}</td>'
                           f'<td class="ty">{esc(r["type"])}</td><td class="cd">{esc(r["code"])}</td><td><span class="camp">{chips}</span></td><td class="p">{pg}</td></tr>')
            title = mm or "Specialized & industry programs (not in a meta major)"
            blocks.append(f'<div class="mm"><h2 id="mm-{slug(title)}">{esc(title)} <span>{len(rows)} programs</span></h2>'
                          f'<table class="tbl"><thead><tr><th>Program</th><th>Department</th><th>Type</th><th>Code</th><th>Offered</th><th>Page</th></tr></thead><tbody>{"".join(trs)}</tbody></table></div>')
        secs.append(f'<section class="front program-index" id="program-index"><h1 class="page-title">Programs by Meta Major</h1>'
                    f'<p class="lede">All {len(registry)} degrees, certificates, and transfer pathways, grouped the way students browse them at my.iecc.edu/metamajors.</p>{"".join(blocks)}</section>')
        toc_entries.append(("", "Programs by Meta Major", "program-index", [(m or "Specialized & industry programs", f"mm-{slug(m or 'Specialized & industry programs (not in a meta major)')}") for m, r in groups.items() if r]))
    secs.append('<section class="placeholder-page" id="district-map"><h1>District Map</h1><p>Placeholder · drop in the district map artwork</p></section>')
    toc_entries.append(("", "District Map", "district-map", []))
    back_cols = "".join(f'<div style="border-color:{COLLEGE_COLOR[c["code"]]}"><h3>{esc(c["name"])}</h3>{esc(c["city"])}<br>{esc(c["phone"])}</div>' for c in cat["colleges"])
    back = (f'<section class="back" aria-label="Back cover"><div class="stripes diag">{stripes_diag()}</div>'
            f'<div class="block"><h2>{esc(cat["district"])}</h2><div class="row">{back_cols}</div><div class="url">{esc(cat["url"])}</div></div></section>')

    # ---- contents
    toc_items = []
    for num, title, aid, subs in toc_entries:
        sub = "".join(f'<li><a href="#{a}">{esc(t)}</a></li>' for t, a in subs[:14]) if subs else ""
        toc_items.append(f'<li class="sec"><a href="#{aid}"><span class="n">{num}</span>{esc(title)}</a>{f"<ul>{sub}</ul>" if sub else ""}</li>')
    toc = f'<section class="toc"><h1>Contents</h1><ol>{"".join(toc_items)}</ol></section>'

    doc = (f'<!doctype html><html lang="en"><head><meta charset="utf-8"><title>{esc(cat["year"])} {esc(cat["title"])} · {esc(cat["district"])}</title>'
           f'<meta name="author" content="{esc(cat["district"])}"><link rel="stylesheet" href="catalog.css"></head><body>'
           f'{cover}{contacts}{toc}{"".join(front)}{"".join(secs)}{back}</body></html>')
    return doc, stats


def write_book(courses, prefixes, content_dir: Path, out_dir: Path, logo: Path | None = None) -> tuple[Path, dict]:
    from weasyprint import HTML

    out_dir.mkdir(parents=True, exist_ok=True)
    doc, stats = build_book_html(courses, prefixes, content_dir, logo)
    (out_dir / "full-catalog.html").write_text(doc, encoding="utf-8")
    pdf = out_dir / "full-catalog.pdf"
    HTML(string=doc, base_url=str(ASSETS)).write_pdf(pdf, pdf_variant="pdf/ua-1")
    return pdf, stats
