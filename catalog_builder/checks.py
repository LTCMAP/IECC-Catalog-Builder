"""Data-quality checks run before every build. Deterministic rules only."""
from __future__ import annotations

import re
from collections import defaultdict
from dataclasses import dataclass

from .model import Course, REQ_RE, BAD_APOS


@dataclass
class Finding:
    severity: str      # "error" | "warning" | "info"
    rule: str
    code: str
    message: str


STANDARD_LABELS = {"PREREQUISITE:", "PREREQUISITES:", "CO-REQUISITE:"}


def run_checks(courses: list[Course], meta: dict, prefixes: dict, print_cmp: dict | None) -> list[Finding]:
    out: list[Finding] = []
    add = lambda sev, rule, code, msg: out.append(Finding(sev, rule, code, msg))
    codes = {c.code for c in courses}

    if meta.get("found") and meta["found"] != len(courses):
        add("warning", "Export count", "—", f"FileMaker reported {meta['found']} found records but the file contains {len(courses)} rows. Re-run the export and confirm nothing was skipped.")

    seen = set()
    for c in courses:
        r = c.raw
        if c.code in seen:
            add("error", "Duplicate course code", c.code, "Course code appears more than once in the export.")
        seen.add(c.code)
        if not re.fullmatch(r"[A-Z]{3} \d{4}", c.code):
            add("error", "Course code format", c.code, "Course code should be 3 letters, a space, and 4 digits.")
        if not r.get("CRSM_DESCRIPTION", "").strip():
            add("error", "Missing description", c.code, f"{c.title} has no description.")
        if re.search(r"\b(draft|tbd|placeholder|lorem)\b", c.title + " " + r.get("CRSM_DESCRIPTION", ""), re.I):
            add("error", "Placeholder text", c.code, f"Title or description contains draft/placeholder wording: “{c.title}”.")
        if c.prefix not in prefixes:
            add("warning", "Prefix not in prefix list", c.code, f"Prefix {c.prefix} is missing from the catalog's Course Prefixes list.")
        if c.credits <= 0:
            add("error", "Credit hours", c.code, "Credit hours are zero or missing.")

        var_raw = r.get("CRSM_CREDIT_VARIABLE", "").strip()
        if var_raw not in ("Y", "N"):
            add("warning", "Variable-credit flag", c.code, f"CRSM_CREDIT_VARIABLE is “{var_raw}” (expected Y or N).")
        if "LectureInternship" in r.get("CRSM_DESCRIPTION_APPEND", ""):
            add("warning", "Delivery type typo", c.code, "Closing tag reads “LectureInternship” (missing separator). Shown as “Lecture / Internship”.")

        for camp in ("FCC", "LTC", "OCC", "WVC"):
            v = r.get(f"CRSM_COLLEGE_{camp}", "")
            if v and v not in ("X", ""):
                add("info", "Campus field formatting", c.code, f"{camp} field contains “{v!r}” instead of a plain X (auto-cleaned).")

        raw_title = r.get("CRSM_TITLE_COURSE", "")
        if raw_title != raw_title.strip() or "  " in raw_title:
            add("info", "Title spacing", c.code, f"Title has extra spaces: “{raw_title}” (auto-cleaned).")

        desc = r.get("CRSM_DESCRIPTION", "")
        for m in BAD_APOS.finditer(desc + " " + r.get("CRSM_TITLE_COURSE", "")):
            src = (desc + " " + r.get("CRSM_TITLE_COURSE", ""))
            add("warning", "Broken apostrophe (encoding)", c.code, f"“…{src[max(0, m.start()-25):m.end()+8]}…” has a ? where an apostrophe belongs. Auto-fixed in output; please fix in FileMaker (the printed catalog was corrected by hand, FileMaker never was).")
        for m in REQ_RE.finditer(desc):
            label = m.group(0).strip()
            if label not in STANDARD_LABELS:
                add("warning", "Requisite label", c.code, f"Non-standard label “{label}”. Standard is PREREQUISITE: / CO-REQUISITE:.")
        if desc.strip() and not desc.rstrip().endswith((".", ")", "!", "?", "\"", "”")):
            add("warning", "Description ending", c.code, f"Description doesn't end with punctuation: “…{desc.strip()[-60:]}”")
        for m in re.finditer(r"\b([A-Z]{3}) ?(\d{4})\b", desc):
            ref = f"{m.group(1)} {m.group(2)}"
            if ref not in codes and m.group(1) not in ("CFR",):
                add("warning", "Reference to missing course", c.code, f"Description mentions {ref}, which is not in this export.")

        if c.delivery not in ("Internship", "Clinical", "Lecture / Internship") and c.lecture is not None and c.lab is not None:
            if abs((c.lecture + c.lab) - c.credits) > 0.01:
                add("warning", "Credit split", c.code, f"Lecture ({c.lecture:g}) + lab ({c.lab:g}) ≠ credit hours ({c.credits:g}).")
        if "Lab" in c.delivery and (c.lab or 0) == 0 and c.delivery != "Lecture / Internship":
            add("info", "Lab hours", c.code, f"Delivery is “{c.delivery}” but lab credit is 0.")

    # Duplicates across courses
    by_title, by_desc = defaultdict(list), defaultdict(list)
    for c in courses:
        by_title[c.title.lower()].append(c.code)
        if c.description:
            by_desc[c.description.lower()].append(c.code)
    for t, cs in by_title.items():
        if len(cs) > 1 and len({x[:3] for x in cs}) == 1:
            add("warning", "Same title, same subject", ", ".join(cs), f"Courses share the title “{t}”. Confirm both are needed or add I / II.")
        elif len(cs) > 1:
            add("info", "Cross-listed title", ", ".join(cs), f"Same title “{t}” under different prefixes (cross-listed?).")
    for d, cs in by_desc.items():
        if len(cs) > 1:
            add("info", "Identical descriptions", ", ".join(cs), "These courses have word-for-word identical descriptions.")

    # Comparison with the printed catalog
    if print_cmp:
        for code in print_cmp.get("printed_twice", []):
            add("error", "Printed twice (2026–27 PDF)", code, "This course is printed twice in the current catalog.")
        for code, fm, pr in print_cmp.get("credit_differences", []):
            add("warning", "Credits differ from print", code, f"FileMaker says {fm:g} cr; the 2026–27 catalog prints {pr:g} cr.")
        titles = {c.code: c.title for c in courses}
        for code, printed in print_cmp.get("title_differences_printed", {}).items():
            add("warning", "Title differs from print", code, f"FileMaker: “{titles.get(code, '?')}” · Printed: “{printed}”.")
        for item in print_cmp.get("printed_not_in_filemaker", []):
            sev = "error" if "DRAFT" in item else "warning"
            add(sev, "Printed but not in FileMaker", item[:8], f"{item[9:]} is in the 2026–27 catalog but not in this export (retired, or missing from the found set?).")
        for code in print_cmp.get("filemaker_not_printed", []):
            t = titles.get(code, "")
            add("warning", "In FileMaker but not printed", code, f"{t} is in FileMaker but not in the 2026–27 catalog (new since June 30, or left out?).")

    order = {"error": 0, "warning": 1, "info": 2}
    out.sort(key=lambda f: (order[f.severity], f.rule, f.code))
    return out
