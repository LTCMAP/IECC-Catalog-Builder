"""Writers: print PDF (WeasyPrint), InDesign Tagged Text, web HTML, data files, report."""
from __future__ import annotations

import csv
import html
import json
import re
from collections import Counter, OrderedDict
from datetime import datetime
from pathlib import Path

from .model import CAMPUSES, Course

ASSETS = Path(__file__).parent / "assets"
esc = html.escape


def group_by_subject(courses: list[Course], prefixes: dict) -> "OrderedDict[str, list[Course]]":
    groups: OrderedDict[str, list[Course]] = OrderedDict()
    for c in courses:
        groups.setdefault(c.prefix, []).append(c)
    return groups


def subject_name(prefix: str, prefixes: dict) -> str:
    return prefixes.get(prefix, prefix)


# ---------------------------------------------------------------- shared bits
def campus_boxes(c: Course) -> str:
    cells = []
    for code, letter, name in CAMPUSES:
        if code in c.campuses:
            cells.append(f'<i class="on {code}" title="{name}">{letter}</i>')
        else:
            cells.append('<i aria-hidden="true"></i>')
    offered = ", ".join(n for code, _, n in CAMPUSES if code in c.campuses)
    return f'<span class="camp" aria-label="Offered at {esc(offered)}">{"".join(cells)}</span>'


def tags(c: Course) -> list[tuple[str, str]]:
    t: list[tuple[str, str]] = []
    if c.delivery:
        t.append(("", c.delivery))
    if c.repeatable:
        t.append(("", f"Repeatable {c.repeatable}×"))
    for code in c.iai:
        t.append(("iai", f"IAI {code}"))
    return t


def credit_text(c: Course) -> str:
    unit = "cr"
    return f"Up to {c.credits_label} {unit}" if c.variable else f"{c.credits_label} {unit}"


# ---------------------------------------------------------------- print (PDF)
def course_html(c: Course) -> str:
    tag_html = "".join(f'<span class="tag {k}">{esc(v)}</span>' for k, v in tags(c))
    req = ""
    if c.prerequisite:
        req += f'<p class="req"><b>Prerequisite</b>{esc(c.prerequisite)}</p>'
    if c.corequisite:
        req += f'<p class="req"><b>Corequisite</b>{esc(c.corequisite)}</p>'
    var = " var" if c.variable else ""
    return (
        f'<article class="course" id="c-{c.prefix}{c.number}">'
        f'<div class="top"><h3><span class="code">{esc(c.code)}</span>{esc(c.title)}</h3><span class="cr{var}">{esc(credit_text(c))}</span></div>'
        f'<div class="meta">{campus_boxes(c)}{tag_html}</div>'
        f'<p class="desc">{esc(c.description)}</p>{req}</article>'
    )


def write_print(courses, prefixes, out_dir: Path, sample_prefixes: list[str] | None = None) -> list[Path]:
    """Course-descriptions section on its own (brand styles). The full book is book.write_book()."""
    from weasyprint import HTML
    from .book import courses_html

    out_dir.mkdir(parents=True, exist_ok=True)
    written = []
    sets = [("course-descriptions.pdf", courses)]
    if sample_prefixes:
        sets.append(("course-descriptions-sample.pdf", [c for c in courses if c.prefix in sample_prefixes]))
    for name, cs in sets:
        body, _ = courses_html(cs, prefixes)
        doc = ('<!doctype html><html lang="en"><head><meta charset="utf-8"><title>Course Descriptions | IECC Academic Catalog</title>'
               '<link rel="stylesheet" href="catalog.css"></head><body>' + body + "</body></html>")
        HTML(string=doc, base_url=str(ASSETS)).write_pdf(out_dir / name, pdf_variant="pdf/ua-1")
        written.append(out_dir / name)
    return written


# ---------------------------------------------------------------- InDesign Tagged Text
PARA_STYLES = OrderedDict([
    ("Subject Head", "<cFont:Jost><cTypeface:Medium><cSize:12.000000><cLeading:15.000000><pSpaceBefore:14.000000><pSpaceAfter:6.000000>"),
    ("Course Head", "<cFont:Jost><cTypeface:Medium><cSize:8.900000><cLeading:11.000000><pSpaceBefore:6.000000><pSpaceAfter:2.500000>"),
    ("Course Meta", "<cFont:Jost><cTypeface:Medium><cSize:6.600000><cLeading:9.000000><pSpaceAfter:3.000000>"),
    ("Course Description", "<cFont:EB Garamond><cTypeface:Regular><cSize:8.400000><cLeading:11.600000>"),
    ("Course Requisite", "<cFont:EB Garamond><cTypeface:Regular><cSize:7.900000><cLeading:10.500000><pSpaceBefore:3.000000>"),
])
CHAR_STYLES = OrderedDict([
    ("Course Code", "<cFont:Jost><cTypeface:Bold><cSize:8.600000>"),
    ("Credits", "<cFont:Jost><cTypeface:SemiBold><cSize:7.000000>"),
    ("Campus On", "<cFont:Jost><cTypeface:SemiBold>"),
    ("Campus Off", "<cFont:Jost><cTypeface:Regular>"),
    ("IAI", "<cFont:Jost><cTypeface:SemiBold>"),
    ("Requisite Label", "<cFont:Jost><cTypeface:SemiBold><cSize:6.800000>"),
])


def tt_escape(s: str) -> str:
    s = s.replace("\\", "\\\\").replace("<", "\\<").replace(">", "\\>")
    return "".join(ch if ord(ch) < 128 else f"<0x{ord(ch):04X}>" for ch in s)


def write_tagged_text(courses, prefixes, out_dir: Path) -> list[Path]:
    """One file per subject (so each can be placed + linked separately) plus one all-in-one file."""
    out_dir.mkdir(parents=True, exist_ok=True)
    header = ["<ASCII-WIN>", "<Version:16><FeatureSet:InDesign-Roman>"]
    for name, spec in CHAR_STYLES.items():
        header.append(f"<DefineCharStyle:{name}={spec}>")
    for name, spec in PARA_STYLES.items():
        header.append(f"<DefineParaStyle:{name}=<Nextstyle:{name}>{spec}>")

    def course_lines(c: Course) -> list[str]:
        RIT = "<0x0008>"  # right-indent tab: pushes credits to the right edge of the column
        camp = "".join(
            f"<CharStyle:Campus On>{l}<CharStyle:> " if code in c.campuses else "<CharStyle:Campus Off><0x00B7><CharStyle:> "
            for code, l, _ in CAMPUSES
        )
        meta = [tt_escape(v) if k != "iai" else f"<CharStyle:IAI>{tt_escape(v)}<CharStyle:>" for k, v in tags(c)]
        lines = [
            f"<ParaStyle:Course Head><CharStyle:Course Code>{tt_escape(c.code)}<CharStyle:>  {tt_escape(c.title)}{RIT}<CharStyle:Credits>{tt_escape(credit_text(c).upper())}<CharStyle:>",
            f"<ParaStyle:Course Meta>{camp}  " + "  <0x00B7>  ".join(meta),
            f"<ParaStyle:Course Description>{tt_escape(c.description)}",
        ]
        if c.prerequisite:
            lines.append(f"<ParaStyle:Course Requisite><CharStyle:Requisite Label>PREREQUISITE<CharStyle:>  {tt_escape(c.prerequisite)}")
        if c.corequisite:
            lines.append(f"<ParaStyle:Course Requisite><CharStyle:Requisite Label>COREQUISITE<CharStyle:>  {tt_escape(c.corequisite)}")
        return lines

    written = []
    all_lines = list(header)
    for p, cs in group_by_subject(courses, prefixes).items():
        body = [f"<ParaStyle:Subject Head>{p}<0x2003>{tt_escape(subject_name(p, prefixes))}"]
        for c in cs:
            body += course_lines(c)
        f = out_dir / f"{p}.txt"
        f.write_text("\r\n".join(header + body) + "\r\n", encoding="ascii")
        written.append(f)
        all_lines += body
    f = out_dir / "_ALL-COURSES.txt"
    f.write_text("\r\n".join(all_lines) + "\r\n", encoding="ascii")
    written.append(f)
    return written


# ---------------------------------------------------------------- data files
def write_data(courses, prefixes, out_dir: Path) -> list[Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    data = [dict(c.to_public(), subject=subject_name(c.prefix, prefixes)) for c in courses]
    j = out_dir / "courses.json"
    j.write_text(json.dumps(data, indent=1, ensure_ascii=False), encoding="utf-8")
    cfile = out_dir / "courses.csv"
    cols = ["code", "prefix", "number", "subject", "title", "credits", "variable", "delivery", "repeatable",
            "campuses", "iai", "prerequisite", "corequisite", "level", "classification", "description"]
    with cfile.open("w", newline="", encoding="utf-8-sig") as fh:
        w = csv.DictWriter(fh, fieldnames=cols, extrasaction="ignore")
        w.writeheader()
        for d in data:
            d = dict(d, campuses=" ".join(d["campuses"]), iai=" ".join(d["iai"]))
            w.writerow(d)
    return [j, cfile]


# ---------------------------------------------------------------- change detection
TRACKED = ["title", "credits", "variable", "delivery", "repeatable", "campuses", "iai", "description", "prerequisite", "corequisite"]


def diff_snapshots(old: list[dict], new: list[dict]) -> dict:
    o = {d["code"]: d for d in old}
    n = {d["code"]: d for d in new}
    changed = []
    for code in sorted(set(o) & set(n)):
        fields = [(f, o[code].get(f), n[code].get(f)) for f in TRACKED if o[code].get(f) != n[code].get(f)]
        if fields:
            changed.append({"code": code, "title": n[code]["title"], "fields": fields})
    return {
        "added": [n[c] for c in sorted(set(n) - set(o))],
        "removed": [o[c] for c in sorted(set(o) - set(n))],
        "changed": changed,
    }
