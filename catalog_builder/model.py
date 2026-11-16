"""Load a FileMaker FMPXMLRESULT export and normalize it into Course records."""
from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field, asdict

NS = {"f": "http://www.filemaker.com/fmpxmlresult"}
CAMPUSES = [("FCC", "F", "Frontier"), ("LTC", "L", "Lincoln Trail"), ("OCC", "O", "Olney Central"), ("WVC", "W", "Wabash Valley")]

# Second digit of the course number = state classification (per catalog "Course Numbering").
CLASSIFICATION = {
    "1": "Baccalaureate / Transfer",
    "2": "Career & Technical",
    "4": "Developmental",
    "6": "Vocational Skills",
    "7": "Adult Basic Education",
    "8": "Adult Secondary Education",
    "9": "English as a Second Language",
}
LEVEL = {"0": "Pre-college", "1": "First-year", "2": "Second-year"}

# Requisite labels as they appear in FileMaker (all the variants), normalized on output.
REQ_RE = re.compile(
    r"\b(PRE-?\s?REQUISIT(?:E|ES|IES)|Pre-?requisites?|CO-?\s?REQUISITES?|Co-?requisites?)\b\s*:?\s*",
    re.IGNORECASE,
)
DELIVERY_FIX = {"LectureInternship": "Lecture / Internship"}


@dataclass
class Course:
    code: str
    prefix: str
    number: str
    title: str
    credits: float
    credits_label: str
    variable: bool
    lecture: float | None
    lab: float | None
    campuses: list[str]
    iai: list[str]
    description: str          # body text without requisites / closing tags
    prerequisite: str | None
    corequisite: str | None
    delivery: str             # Lecture, Lab, Lecture / Lab, Internship, Clinical...
    repeatable: int | None
    level: str
    classification: str
    raw: dict = field(repr=False, default_factory=dict)
    record_id: str = ""
    mod_id: str = ""

    def to_public(self) -> dict:
        d = asdict(self)
        d.pop("raw")
        return d


BAD_APOS = re.compile(r"(?<=[A-Za-z])\?(?=s\b|[A-Za-z])|(?<=s)\?(?= [a-z])")


def _clean(s: str | None) -> str:
    s = BAD_APOS.sub("’", s or "")  # "Labor?s" -> "Labor’s" (curly apostrophes lost in FileMaker)
    s = (s or "").replace(" ", " ")
    return re.sub(r"[ \t\r\n]+", " ", s).strip()


def fmt_credits(x: float) -> str:
    return f"{x:g}"


def _num(s: str) -> float | None:
    s = (s or "").strip()
    if not s:
        return None
    try:
        return float(s)
    except ValueError:
        return None


def split_requisites(desc: str) -> tuple[str, str | None, str | None]:
    """Pull PREREQUISITE / CO-REQUISITE clauses out of the description body."""
    matches = list(REQ_RE.finditer(desc))
    if not matches:
        return desc, None, None
    body = desc[: matches[0].start()].strip()
    pre, co = [], []
    for i, m in enumerate(matches):
        end = matches[i + 1].start() if i + 1 < len(matches) else len(desc)
        text = desc[m.end():end].strip().rstrip(".").strip()
        if not text:
            continue
        (co if "CO" in m.group(1).upper().replace("-", "")[:2] else pre).append(text)
    return body, ("; ".join(pre) or None), ("; ".join(co) or None)


def parse_append(append: str) -> tuple[str, bool, int | None]:
    a = _clean(append)
    for bad, good in DELIVERY_FIX.items():
        a = a.replace(bad, good)
    parts = [p.strip() for p in a.split(".") if p.strip()]
    delivery = parts[0] if parts else ""
    variable = any(p.lower() == "variable" for p in parts)
    rep = None
    for p in parts:
        m = re.match(r"Repeatable (\d+) times?", p, re.I)
        if m:
            rep = int(m.group(1))
    return delivery, variable, rep


def load_export(path: str) -> tuple[list[Course], dict]:
    root = ET.parse(path).getroot()
    meta = {
        "product": (root.find("f:PRODUCT", NS).attrib if root.find("f:PRODUCT", NS) is not None else {}),
        "database": (root.find("f:DATABASE", NS).attrib if root.find("f:DATABASE", NS) is not None else {}),
        "found": int(root.find("f:RESULTSET", NS).get("FOUND", "0")),
    }
    fields = [f.get("NAME") for f in root.findall(".//f:METADATA/f:FIELD", NS)]
    courses: list[Course] = []
    for row in root.findall(".//f:RESULTSET/f:ROW", NS):
        vals = []
        for col in row.findall("f:COL", NS):
            datas = col.findall("f:DATA", NS)
            vals.append(datas[0].text if datas else "")
        r = dict(zip(fields, [(v or "") for v in vals]))
        code = _clean(r.get("CRSM_SUBNUM"))
        prefix, _, number = code.partition(" ")
        desc_full = _clean(r.get("CRSM_DESCRIPTION"))
        body, pre, co = split_requisites(desc_full)
        delivery, var_from_append, rep = parse_append(r.get("CRSM_DESCRIPTION_APPEND", ""))
        credits = _num(r.get("CRSM_CREDIT_HOURS")) or 0.0
        courses.append(
            Course(
                code=code,
                prefix=prefix,
                number=number,
                title=_clean(r.get("CRSM_TITLE_COURSE")),
                credits=credits,
                credits_label=fmt_credits(credits),
                variable=(r.get("CRSM_CREDIT_VARIABLE", "").strip().upper() == "Y") or var_from_append,
                lecture=_num(r.get("CRSM_CREDIT_LECTURE")),
                lab=_num(r.get("CRSM_CREDIT_LAB")),
                campuses=[c for c, _, _ in CAMPUSES if r.get(f"CRSM_COLLEGE_{c}", "").strip()],
                iai=[_clean(r.get(f"CRSM_IAI_{i}_EXPORT")) for i in range(1, 7) if _clean(r.get(f"CRSM_IAI_{i}_EXPORT"))],
                description=body,
                prerequisite=pre,
                corequisite=co,
                delivery=delivery,
                repeatable=rep,
                level=LEVEL.get(number[:1], "Other"),
                classification=CLASSIFICATION.get(number[1:2], "Other"),
                raw=r,
                record_id=row.get("RECORDID", ""),
                mod_id=row.get("MODID", ""),
            )
        )
    courses.sort(key=lambda c: (c.prefix, c.number))
    return courses, meta
