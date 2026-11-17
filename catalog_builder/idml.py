"""InDesign IDML export of the full catalog.

Builds a real, styled InDesign document (open it in InDesign, save as .indd):
  - Letter pages, one parent page (running head, teal rule, page number)
  - one story per catalog section, each starting on a new page, threaded through enough frames
  - Course Descriptions in two columns, using the same paragraph/character style names as the
    InDesign Tagged Text files (Subject Head, Course Head, Course Meta, ...)
  - real InDesign tables for program semesters, the calendar and the program index
  - brand colors as swatches; fonts set per style (config.json "indesign_fonts" to change them)

Page counts are estimated. Run the bundled "Fit catalog pages.jsx" once in InDesign to add pages
where a section runs long and remove empty ones (Window > Utilities > Scripts, or File > Scripts > Browse).

The package skeleton (Graphic, Preferences, default styles) comes from assets/idml-skeleton,
taken from a document saved by InDesign 2026 so InDesign recognizes every part.
"""
from __future__ import annotations

import html
import math
import re
import zipfile
from html.parser import HTMLParser
from pathlib import Path
from xml.sax.saxutils import escape as xesc

from .model import CAMPUSES, Course
from .outputs import ASSETS, credit_text, group_by_subject, subject_name

SKELETON = ASSETS / "idml-skeleton"
NS = 'xmlns:idPkg="http://ns.adobe.com/AdobeInDesign/idml/1.0/packaging" DOMVersion="21.2"'
HEAD = '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'

PAGE_W, PAGE_H = 612.0, 792.0
MARGIN = {"top": 66.0, "bottom": 60.0, "left": 54.0, "right": 54.0}
FRAME = (MARGIN["left"], MARGIN["top"], PAGE_W - MARGIN["right"], PAGE_H - MARGIN["bottom"])  # x0, y0, x1, y1
GUTTER = 18.0

DEFAULT_FONTS = {
    "sans": {"family": "Futura PT", "regular": "Book", "medium": "Medium", "semibold": "Medium", "bold": "Bold", "italic": "Book Oblique"},
    "serif": {"family": "EB Garamond", "regular": "Regular", "medium": "Medium", "semibold": "SemiBold", "bold": "Bold", "italic": "Italic"},
}

COLORS = {  # name: (R, G, B)
    "IECC Teal": (2, 119, 137), "IECC Teal Tint": (227, 240, 242), "FCC Gold": (243, 208, 62), "LTC Green": (21, 71, 52),
    "OCC Navy": (40, 51, 69), "WVC Red": (206, 32, 47), "Catalog Ink": (29, 33, 36), "Catalog Gray": (83, 91, 93),
}
CAMPUS_COLOR = {"FCC": "FCC Gold", "LTC": "LTC Green", "OCC": "OCC Navy", "WVC": "WVC Red"}

# paragraph styles: name -> (font, weight, size, leading, extra attributes)
P = {
    "Cover District": ("sans", "medium", 13, 16, {"Capitalization": "AllCaps", "Tracking": "160", "FillColor": "IECC Teal"}),
    "Cover Year": ("sans", "medium", 30, 34, {"FillColor": "IECC Teal", "SpaceBefore": "36"}),
    "Cover Title": ("sans", "medium", 58, 58, {"Capitalization": "AllCaps", "SpaceAfter": "24"}),
    "Cover Body": ("serif", "regular", 13, 18, {"SpaceAfter": "6"}),
    "Running Head": ("sans", "medium", 7.5, 9, {"Capitalization": "AllCaps", "Tracking": "120", "FillColor": "Catalog Gray"}),
    "Folio": ("sans", "medium", 8, 10, {"Justification": "RightAlign", "FillColor": "IECC Teal"}),
    "Kicker": ("sans", "medium", 8.5, 11, {"Capitalization": "AllCaps", "Tracking": "150", "FillColor": "IECC Teal", "SpaceAfter": "2"}),
    "Section Title": ("sans", "medium", 30, 34, {"SpaceAfter": "16", "RuleBelow": True, "KeepWithNext": "2"}),
    "Heading 2": ("sans", "medium", 15, 18, {"FillColor": "IECC Teal", "SpaceBefore": "16", "SpaceAfter": "5", "KeepWithNext": "2"}),
    "Heading 3": ("sans", "medium", 12, 15, {"SpaceBefore": "11", "SpaceAfter": "3", "KeepWithNext": "2"}),
    "Heading 4": ("sans", "semibold", 10.5, 13, {"SpaceBefore": "8", "SpaceAfter": "2", "KeepWithNext": "1"}),
    "Body": ("serif", "regular", 10.5, 14, {"SpaceAfter": "6"}),
    "Lede": ("serif", "regular", 12.5, 17, {"SpaceAfter": "10", "FillColor": "Catalog Gray"}),
    "Bullet": ("serif", "regular", 10.5, 14, {"SpaceAfter": "3", "LeftIndent": "14", "FirstLineIndent": "-10", "BulletsAndNumberingListType": "BulletList"}),
    "Numbered": ("serif", "regular", 10.5, 14, {"SpaceAfter": "3", "LeftIndent": "16", "FirstLineIndent": "-16", "BulletsAndNumberingListType": "NumberedList"}),
    "Source Note": ("sans", "regular", 8.5, 11, {"FillColor": "IECC Teal", "LeftIndent": "8", "SpaceBefore": "2", "SpaceAfter": "10"}),
    "Placeholder": ("sans", "medium", 9.5, 12, {"FillColor": "IECC Teal", "SpaceAfter": "8"}),
    "Table Head": ("sans", "medium", 7.5, 9.5, {"Capitalization": "AllCaps", "Tracking": "80", "FillColor": "Paper"}),
    "Table Body": ("sans", "regular", 8.5, 11, {}),
    "Table Credits": ("sans", "medium", 8.5, 11, {"Justification": "RightAlign"}),
    "Program Title": ("sans", "medium", 20, 23, {"SpaceAfter": "4", "KeepWithNext": "2"}),
    "Program Meta": ("sans", "medium", 8, 11, {"Capitalization": "AllCaps", "Tracking": "60", "FillColor": "Catalog Gray", "SpaceAfter": "6"}),
    "Program Description": ("serif", "regular", 10.5, 14, {"SpaceAfter": "8"}),
    "Term Head": ("sans", "medium", 8.5, 11, {"Capitalization": "AllCaps", "Tracking": "80", "FillColor": "IECC Teal", "SpaceBefore": "8", "SpaceAfter": "3", "KeepWithNext": "1"}),
    "Program Total": ("sans", "medium", 9.5, 12, {"Capitalization": "AllCaps", "Tracking": "80", "SpaceBefore": "8", "SpaceAfter": "6", "RuleAbove": True}),
    "Notes": ("sans", "regular", 8, 10.5, {"FillColor": "Catalog Gray", "SpaceAfter": "3"}),
    # course descriptions (same names as the Tagged Text files)
    "Subject Head": ("sans", "medium", 12, 15, {"SpaceBefore": "14", "SpaceAfter": "6", "KeepWithNext": "2", "RuleBelow": True}),
    "Course Head": ("sans", "medium", 8.9, 11, {"SpaceBefore": "6", "SpaceAfter": "1.5", "KeepWithNext": "2"}),
    "Course Meta": ("sans", "medium", 6.8, 9, {"SpaceAfter": "2.5", "KeepWithNext": "1", "FillColor": "Catalog Gray"}),
    "Course Description": ("serif", "regular", 8.6, 11.4, {}),
    "Course Requisite": ("serif", "regular", 8, 10.5, {"SpaceBefore": "2.5"}),
}
# character styles: name -> (font or None, weight or None, extra attributes)
C = {
    "Bold": (None, "bold", {}),
    "Italic": (None, "italic", {}),
    "Course Code": ("sans", "bold", {"FillColor": "IECC Teal"}),
    "Credits": ("sans", "semibold", {"FillColor": "IECC Teal"}),
    "Campus FCC": ("sans", "bold", {"FillColor": "FCC Gold"}),
    "Campus LTC": ("sans", "bold", {"FillColor": "LTC Green"}),
    "Campus OCC": ("sans", "bold", {"FillColor": "OCC Navy"}),
    "Campus WVC": ("sans", "bold", {"FillColor": "WVC Red"}),
    "IAI": ("sans", "semibold", {"FillColor": "Catalog Ink"}),
    "Requisite Label": ("sans", "semibold", {"Capitalization": "AllCaps", "FillColor": "IECC Teal"}),
    "Superscript": (None, None, {"Position": "Superscript"}),
    "Or": ("sans", "semibold", {"Capitalization": "AllCaps", "FillColor": "IECC Teal"}),
    "Missing": ("sans", "semibold", {"FillColor": "WVC Red"}),
}
STYLE_FONT_ROLE = {k: v[0] for k, v in P.items()}

ACE_RIGHT_TAB = "\x00RIGHTTAB\x00"   # becomes <?ACE 8?> (right indent tab)
ACE_PAGE = "\x00PAGE\x00"            # becomes <?ACE 18?> (current page number)


class Ids:
    def __init__(self, start=0x200000):
        self.n = start

    def __call__(self) -> str:
        self.n += 1
        return f"u{self.n:x}"


# ------------------------------------------------------------------ HTML -> blocks
class _Blocks(HTMLParser):
    """Turns the catalog's HTML fragments into paragraphs [(style, runs)] and tables."""
    SKIP = {"svg", "script", "style", "nav", "img"}
    SKIP_CLASS = {"stripes", "bar", "auto", "legend", "pg", "brandline", "art"}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.blocks: list = []
        self.stack: list[tuple[str, set]] = []
        self.skip = 0
        self.para: tuple[str, list] | None = None
        self.char: list[str] = []
        self.table: list | None = None   # rows: [(is_head, [cell runs...])]
        self.row: list | None = None
        self.cell: list | None = None
        self.cell_style = "Table Body"
        self.th_parts: list[str] | None = None

    # helpers
    def _in(self, cls: str) -> bool:
        return any(cls in c for _, c in self.stack)

    def _target(self) -> list | None:
        if self.cell is not None:
            return self.cell
        if self.para is not None:
            return self.para[1]
        return None

    def _start_para(self, style: str):
        self._end_para()
        self.para = (style, [])

    def _end_para(self):
        if self.para and "".join(t for t, _ in self.para[1]).strip():
            runs = _trim(self.para[1])
            self.blocks.append(("p", self.para[0], runs))
        self.para = None

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        cls = set((a.get("class") or "").split())
        if tag in ("br", "hr", "wbr", "meta", "link", "input"):
            if tag == "br":
                t = self._target()
                if t is not None:
                    t.append((" ", None))
            return
        self.stack.append((tag, cls))
        if self.skip or tag in self.SKIP or cls & self.SKIP_CLASS or a.get("aria-hidden") == "true":
            self.skip += 1
            return
        if tag == "i" and "on" in cls:
            camp = next((c for c in cls if c in CAMPUS_COLOR), None)
            self.char.append(f"Campus {camp}" if camp else "")
            return
        if tag == "i" and not cls:
            self.char.append("Italic")
            return
        if tag in ("b", "strong") and self.th_parts and self.para:
            self.para[1].append((ACE_RIGHT_TAB, None))
        if tag in ("b", "strong"):
            self.char.append("Bold"); return
        if tag == "em":
            self.char.append("Italic"); return
        if tag == "sup":
            self.char.append("Superscript"); return
        if tag == "span" and "or" in cls:
            self.char.append("Or"); self._text(" "); return
        if tag == "span" and "missing" in cls:
            self.char.append("Missing"); self._text(" "); return
        if tag == "span" and "code" in cls:
            self.char.append("Course Code"); return
        if tag == "span" and "camp" in cls:
            self.char.append(""); return
        if tag == "span" and self.th_parts is not None and self.para:
            if self.th_parts:
                self.para[1].append((ACE_RIGHT_TAB, None))
            self.th_parts.append(1)
            return
        if tag == "table":
            self._end_para()
            self.table = []
            return
        if tag == "tr" and self.table is not None:
            self.row = []
            return
        if tag in ("td", "th") and self.row is not None:
            self.cell = []
            self.cell_head = tag == "th"
            self.cell_cls = cls
            if "c" in cls:
                self.char.append("Course Code")
            return
        if self.cell is not None:
            return
        # block-level
        if tag == "h1":
            self._start_para("Section Title")
        elif tag == "h2":
            self._start_para("Program Title" if self._in("program") else "Term Head" if self._in("calendar") else "Heading 2")
        elif tag == "h3":
            self._start_para("Heading 3")
        elif tag in ("h4", "h5", "h6"):
            self._start_para("Heading 4")
        elif tag == "p":
            style = "Body"
            if "desc" in cls and self._in("program"):
                style = "Program Description"
            elif cls & {"lede", "intro"}:
                style = "Lede"
            elif "notes" in cls:
                style = "Notes"
            self._start_para(style)
        elif tag == "li":
            ordered = any(t == "ol" for t, _ in self.stack[:-1])
            self._start_para("Numbered" if ordered else "Bullet")
        elif tag == "blockquote":
            self._start_para("Source Note")
        elif tag == "div":
            if "todo" in cls:
                self._start_para("Placeholder")
                self.para[1].append(("Placeholder: ", "Bold"))
            elif "kicker" in cls:
                self._start_para("Kicker")
            elif "meta" in cls and self._in("program"):
                self._start_para("Program Meta")
            elif "th" in cls:
                self._start_para("Term Head")
                self.th_parts = []
            elif "total" in cls:
                self._start_para("Program Total")
                self.th_parts = []
            elif "notes" in cls:
                self._start_para("Notes")

    def handle_endtag(self, tag):
        if tag in ("br", "hr", "wbr", "meta", "link", "input"):
            return
        # pop to matching tag
        while self.stack:
            t, cls = self.stack.pop()
            if self.skip:
                self.skip -= 1
                if t == tag:
                    return
                continue
            self._close(t, cls)
            if t == tag:
                return

    def _close(self, tag, cls):
        if tag == "i" and ("on" in cls or not cls) or tag in ("b", "strong", "em", "sup") \
                or (tag == "span" and cls & {"or", "missing", "code", "camp"}):
            if self.char:
                self.char.pop()
            if tag == "span" and cls & {"or", "missing"}:
                self._text(" ")
            if tag == "span" and "code" in cls:
                self._text(" ")
            if tag == "i" and "on" in cls:
                self._text(" ")
            return
        if tag in ("td", "th") and self.cell is not None:
            if "c" in getattr(self, "cell_cls", set()) and self.char:
                self.char.pop()
            self.row.append((self.cell_head, _trim(self.cell), self.cell_cls))
            self.cell = None
            return
        if tag == "tr" and self.row is not None:
            if self.row and any("".join(t for t, _ in c[1]).strip() for c in self.row):
                self.table.append(self.row)
            self.row = None
            return
        if tag == "table" and self.table is not None:
            if self.table:
                self.blocks.append(("table", self.table))
            self.table = None
            return
        if tag == "div" and "total" in cls:
            self.th_parts = None
        if tag == "div" and "th" in cls:
            self.th_parts = None
            self._end_para()
            return
        if self.cell is None and (tag in ("h1", "h2", "h3", "h4", "h5", "h6", "p", "li", "blockquote")
                                  or (tag == "div" and cls & {"todo", "kicker", "meta", "total", "notes"})):
            self._end_para()

    def _text(self, s):
        t = self._target()
        if t is None:
            return
        style = next((c for c in reversed(self.char) if c), None)
        t.append((s, style))

    def handle_data(self, data):
        if self.skip:
            return
        s = re.sub(r"\s+", " ", data)
        if not s:
            return
        if self._target() is None:
            if not s.strip():
                return
            self._start_para("Body")
        self._text(s)

    def close(self):
        super().close()
        self._end_para()
        return self.blocks


def _trim(runs):
    out = []
    for t, s in runs:
        if out and out[-1][1] == s:
            out[-1] = (out[-1][0] + t, s)
        else:
            out.append((t, s))
    text = "".join(t for t, _ in out)
    if not text.strip():
        return []
    # collapse doubled spaces across runs, trim ends
    res, prev_space = [], True
    for t, s in out:
        t = re.sub(r" {2,}", " ", t)
        if prev_space:
            t = t.lstrip(" ")
        if t:
            res.append((t, s))
            prev_space = t.endswith(" ")
    if res:
        res[-1] = (res[-1][0].rstrip(" "), res[-1][1])
    return [r for r in res if r[0]]


def html_blocks(fragment: str) -> list:
    p = _Blocks()
    p.feed(fragment)
    return p.close()


# ------------------------------------------------------------------ course blocks
def course_blocks(courses: list[Course], prefixes: dict) -> list:
    out = []
    for p, cs in group_by_subject(courses, prefixes).items():
        out.append(("p", "Subject Head", [(f"{p}  ", "Course Code"), (subject_name(p, prefixes), None)]))
        for c in cs:
            out.append(("p", "Course Head", [(c.code, "Course Code"), ("  " + c.title, None), (ACE_RIGHT_TAB, None),
                                            (credit_text(c), "Credits")]))
            meta = []
            for code, letter, _ in CAMPUSES:
                if code in c.campuses:
                    meta.append((letter + " ", f"Campus {code}"))
            bits = [b for b in [c.delivery, f"Repeatable {c.repeatable}×" if c.repeatable else ""] if b]
            if bits:
                meta.append(("· " + " · ".join(bits), None))
            for i in c.iai:
                meta.append(("  IAI " + i, "IAI"))
            if meta:
                out.append(("p", "Course Meta", meta))
            if c.description:
                out.append(("p", "Course Description", [(c.description, None)]))
            if c.prerequisite:
                out.append(("p", "Course Requisite", [("Prerequisite: ", "Requisite Label"), (c.prerequisite, None)]))
            if c.corequisite:
                out.append(("p", "Course Requisite", [("Corequisite: ", "Requisite Label"), (c.corequisite, None)]))
    return out


# ------------------------------------------------------------------ XML writers
def _content(text: str) -> str:
    parts = re.split(f"({ACE_RIGHT_TAB}|{ACE_PAGE})", text)
    out = []
    for p in parts:
        if p == ACE_RIGHT_TAB:
            out.append("<?ACE 8?>")
        elif p == ACE_PAGE:
            out.append("<?ACE 18?>")
        elif p:
            out.append(xesc(re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\u2028\u2029]", " ", p)))
    return "<Content>" + "".join(out) + "</Content>"


def _csr(runs, last: bool, extra: str = "") -> str:
    xs = []
    for i, (t, s) in enumerate(runs):
        cs = f"CharacterStyle/{xesc(s)}" if s else "CharacterStyle/$ID/[No character style]"
        br = "" if (last or i < len(runs) - 1) else "<Br/>"
        xs.append(f'<CharacterStyleRange AppliedCharacterStyle="{cs}"{extra}>{_content(t)}{br}</CharacterStyleRange>')
    return "".join(xs)


def _table_xml(rows, ids: Ids, width: float, last: bool) -> str:
    ncol = max(len(r) for r in rows)
    head = 1 if rows and all(c[0] for c in rows[0]) else 0
    # program-index tables: drop the trailing "Page" column (page numbers are an InDesign cross-reference job)
    if head and "".join(t for t, _ in rows[0][-1][1]).strip().lower() == "page":
        rows = [r[:-1] for r in rows]
        ncol -= 1
    lens = [0] * ncol
    for r in rows:
        for i, c in enumerate(r[:ncol]):
            lens[i] = max(lens[i], min(60, len("".join(t for t, _ in c[1]))))
    # fixed widths for known column kinds (course code, credits, calendar month/day); the rest share what's left
    FIXED = {"c": 62.0, "cr": 38.0, "m": 70.0, "d": 56.0, "cd": 46.0, "ty": 62.0}
    kinds = [None] * ncol
    for r in rows:
        for i, c in enumerate(r[:ncol]):
            k = next((k for k in FIXED if k in c[2]), None)
            if k and kinds[i] is None:
                kinds[i] = k
    fixed_total = sum(FIXED[k] for k in kinds if k)
    free = [i for i in range(ncol) if not kinds[i]]
    if free and fixed_total < width * 0.8:
        weights = {i: max(5, lens[i]) for i in free}
        tw = sum(weights.values())
        widths = [FIXED[kinds[i]] if kinds[i] else (width - fixed_total) * weights[i] / tw for i in range(ncol)]
    else:
        weights = [max(5, l) for l in lens]
        tot = sum(weights)
        widths = [max(34.0, width * w / tot) for w in weights]
        scale = width / sum(widths)
        widths = [w * scale for w in widths]
    tid = ids()
    x = [f'<Table Self="{tid}" HeaderRowCount="{head}" FooterRowCount="0" BodyRowCount="{len(rows) - head}" ColumnCount="{ncol}" '
         f'AppliedTableStyle="TableStyle/$ID/[Basic Table]" TableDirection="LeftToRightDirection" '
         f'TopBorderStrokeWeight="0" BottomBorderStrokeWeight="0.5" LeftBorderStrokeWeight="0" RightBorderStrokeWeight="0" '
         f'BottomBorderStrokeColor="Color/IECC Teal Tint">']
    for ri in range(len(rows)):
        x.append(f'<Row Self="{tid}Row{ri}" Name="{ri}" SingleRowHeight="14" MinimumHeight="14" AutoGrow="true"/>')
    for ci, w in enumerate(widths):
        x.append(f'<Column Self="{tid}Column{ci}" Name="{ci}" SingleColumnWidth="{w:.2f}"/>')
    for ri, r in enumerate(rows):
        is_head = head and ri == 0
        for ci in range(ncol):
            c = r[ci] if ci < len(r) else (False, [], set())
            style = "Table Head" if is_head else ("Table Credits" if "cr" in c[2] else "Table Body")
            fill = ' FillColor="Color/IECC Teal"' if is_head else ""
            stroke = ('TopEdgeStrokeWeight="0" LeftEdgeStrokeWeight="0" RightEdgeStrokeWeight="0" BottomEdgeStrokeWeight="0.5" '
                      'BottomEdgeStrokeColor="Color/IECC Teal Tint" LeftEdgeStrokeColor="Swatch/None" RightEdgeStrokeColor="Swatch/None" '
                      'TopEdgeStrokeColor="Swatch/None" ')
            runs = c[1] or [("", None)]
            x.append(f'<Cell Self="{tid}i{ci}_{ri}" Name="{ci}:{ri}" RowSpan="1" ColumnSpan="1" AppliedCellStyle="CellStyle/$ID/[None]" '
                     f'AppliedCellStylePriority="0" {stroke}TopInset="3" BottomInset="3" LeftInset="4" RightInset="4"{fill}>'
                     f'<ParagraphStyleRange AppliedParagraphStyle="ParagraphStyle/{style}">{_csr(runs, True)}</ParagraphStyleRange></Cell>')
    x.append("</Table>")
    br = "" if last else "<Br/>"
    return (f'<ParagraphStyleRange AppliedParagraphStyle="ParagraphStyle/Table Body"><CharacterStyleRange '
            f'AppliedCharacterStyle="CharacterStyle/$ID/[No character style]">{"".join(x)}{br}</CharacterStyleRange></ParagraphStyleRange>')


def story_xml(sid: str, blocks: list, ids: Ids, width: float) -> str:
    body = []
    for i, b in enumerate(blocks):
        last = i == len(blocks) - 1
        if b[0] == "p":
            _, style, runs = b
            body.append(f'<ParagraphStyleRange AppliedParagraphStyle="ParagraphStyle/{xesc(style)}">{_csr(runs, last)}</ParagraphStyleRange>')
        elif b[0] == "table":
            body.append(_table_xml(b[1], ids, width, last))
        elif b[0] == "break":   # frame break: the next paragraph starts on a new page
            body.append('<ParagraphStyleRange AppliedParagraphStyle="ParagraphStyle/Body"><CharacterStyleRange '
                        'AppliedCharacterStyle="CharacterStyle/$ID/[No character style]"><Content><?ACE 12?></Content>'
                        + ("" if last else "<Br/>") + "</CharacterStyleRange></ParagraphStyleRange>")
    return (HEAD + f'<idPkg:Story {NS}><Story Self="{sid}" UserText="true" IsEndnoteStory="false" AppliedTOCStyle="n" TrackChanges="false" '
            f'StoryTitle="$ID/" AppliedNamedGrid="n"><StoryPreference OpticalMarginAlignment="false" OpticalMarginSize="12" '
            f'FrameType="TextFrameType" StoryOrientation="Horizontal" StoryDirection="LeftToRightDirection"/>'
            f'<InCopyExportOption IncludeGraphicProxies="true" IncludeAllResources="false"/>{"".join(body)}</Story></idPkg:Story>')


def _rect_path(x0, y0, x1, y1, closed=True) -> str:
    pts = [(x0, y0), (x0, y1), (x1, y1), (x1, y0)] if closed else [(x0, y0), (x1, y1)]
    pp = "".join(f'<PathPointType Anchor="{x:g} {y:g}" LeftDirection="{x:g} {y:g}" RightDirection="{x:g} {y:g}"/>' for x, y in pts)
    return (f'<Properties><PathGeometry><GeometryPathType PathOpen="{"false" if closed else "true"}"><PathPointArray>{pp}'
            f'</PathPointArray></GeometryPathType></PathGeometry></Properties>')


PAGE_XFORM = f"1 0 0 1 {-PAGE_W / 2:g} {-PAGE_H / 2:g}"


def text_frame(fid, sid, prev, nxt, box, cols=1, layer="ulayer") -> str:
    return (f'<TextFrame Self="{fid}" ParentStory="{sid}" PreviousTextFrame="{prev or "n"}" NextTextFrame="{nxt or "n"}" '
            f'ContentType="TextType" Visible="true" Name="$ID/" ItemLayer="{layer}" Locked="false" '
            f'AppliedObjectStyle="ObjectStyle/$ID/[Normal Text Frame]" ItemTransform="{PAGE_XFORM}">{_rect_path(*box)}'
            f'<TextFramePreference TextColumnCount="{cols}" TextColumnGutter="{GUTTER:g}" TextColumnFixedWidth="{(box[2] - box[0] - (cols - 1) * GUTTER) / cols:.3f}" '
            f'UseFixedColumnWidth="false" FirstBaselineOffset="AscentOffset" VerticalJustification="TopAlign"/></TextFrame>')


def margin_pref() -> str:
    return (f'<MarginPreference ColumnCount="1" ColumnGutter="12" Top="{MARGIN["top"]:g}" Bottom="{MARGIN["bottom"]:g}" '
            f'Left="{MARGIN["left"]:g}" Right="{MARGIN["right"]:g}" ColumnDirection="Horizontal" ColumnsPositions="0 {FRAME[2] - FRAME[0]:g}"/>')


# ------------------------------------------------------------------ styles & swatches
def _font(role, weight, fonts):
    f = fonts[role]
    return f["family"], f.get(weight) or f["regular"]


def styles_xml(fonts) -> tuple[str, str]:
    paras = []
    for name, (role, weight, size, lead, extra) in P.items():
        fam, face = _font(role, weight, fonts)
        attrs = {"Self": f"ParagraphStyle/{name}", "Name": name, "Imported": "false", "NextStyle": f"ParagraphStyle/{name}",
                 "KeyboardShortcut": "0 0", "PointSize": f"{size:g}", "FontStyle": face, "Hyphenation": "true" if role == "serif" else "false",
                 "FillColor": "Color/Catalog Ink"}
        for k, v in extra.items():
            if k in ("RuleBelow", "RuleAbove"):
                attrs.update({f"{k}": "true", f"{k}LineWeight": "1.5" if k == "RuleBelow" else "0.75",
                              f"{k}Color": "Color/IECC Teal", f"{k}Offset": "6" if k == "RuleBelow" else "12"})
            elif k == "FillColor":
                attrs["FillColor"] = "Color/Paper" if v == "Paper" else f"Color/{v}"
            else:
                attrs[k] = v
        a = " ".join(f'{k}="{xesc(str(v))}"' for k, v in attrs.items())
        paras.append(f'<ParagraphStyle {a}><Properties><BasedOn type="object">ParagraphStyle/$ID/[No paragraph style]</BasedOn>'
                     f'<PreviewColor type="enumeration">Nothing</PreviewColor><Leading type="unit">{lead:g}</Leading>'
                     f'<AppliedFont type="string">{xesc(fam)}</AppliedFont></Properties></ParagraphStyle>')
    chars = []
    for name, (role, weight, extra) in C.items():
        attrs = {"Self": f"CharacterStyle/{name}", "Name": name, "Imported": "false", "KeyboardShortcut": "0 0"}
        props = '<PreviewColor type="enumeration">Nothing</PreviewColor>'
        if weight:
            if role:
                fam, face = _font(role, weight, fonts)
                props += f'<AppliedFont type="string">{xesc(fam)}</AppliedFont>'
                attrs["FontStyle"] = face
            else:  # inherit the paragraph's family; serif names are the common case
                attrs["FontStyle"] = fonts["serif"].get(weight, weight.title())
        for k, v in extra.items():
            attrs[k] = f"Color/{v}" if k == "FillColor" else v
        a = " ".join(f'{k}="{xesc(str(v))}"' for k, v in attrs.items())
        chars.append(f'<CharacterStyle {a}><Properties>{props}</Properties></CharacterStyle>')
    return "".join(paras), "".join(chars)


def colors_xml() -> str:
    return "".join(f'<Color Self="Color/{n}" Model="Process" Space="RGB" ColorValue="{r} {g} {b}" ColorOverride="Normal" '
                   f'AlternateSpace="NoAlternateColor" AlternateColorValue="" Name="{n}" ColorEditable="true" ColorRemovable="true" '
                   f'Visible="true" SwatchCreatorID="7937" SwatchColorGroupReference="n"/>' for n, (r, g, b) in COLORS.items())


# ------------------------------------------------------------------ height estimate (pages per section)
def _block_height(b, col_w) -> float:
    if b[0] == "table":
        rows = b[1]
        return sum(max(1, math.ceil(max(len("".join(t for t, _ in c[1])) for c in r) * 4.4 / max(80, col_w / max(1, len(r)) * 1.6))) * 11 + 6
                   for r in rows) + 10
    if b[0] == "break":
        return 0
    style = P.get(b[1], P["Body"])
    _, _, size, lead, extra = style
    text = "".join(t for t, _ in b[2])
    cw = size * (0.47 if style[0] == "serif" else 0.52)
    lines = max(1, math.ceil(len(text) * cw / (col_w - float(extra.get("LeftIndent", 0)))))
    return lines * lead + float(extra.get("SpaceBefore", 0)) + float(extra.get("SpaceAfter", 0))


def estimate_pages(blocks, cols) -> int:
    width = FRAME[2] - FRAME[0]
    col_w = (width - (cols - 1) * GUTTER) / cols
    h = sum(_block_height(b, col_w) for b in blocks)
    cap = (FRAME[3] - FRAME[1]) * cols
    return max(1, math.ceil(h * 1.08 / cap))


# ------------------------------------------------------------------ package
def write_idml(courses: list[Course], prefixes: dict, parts: dict, out_path: Path, fonts: dict | None = None) -> dict:
    fonts = {**DEFAULT_FONTS, **(fonts or {})}
    cat = parts["cat"]
    ids = Ids()
    width = FRAME[2] - FRAME[0]

    # sections -> (title, blocks, columns, cover?)
    sections = []
    colleges = " · ".join(c["name"] for c in cat["colleges"])
    sections.append(("Cover", [("p", "Cover District", [(cat["district"], None)]),
                               ("p", "Cover Year", [(cat["year"], None)]),
                               ("p", "Cover Title", [("Academic Catalog", None)]),
                               ("p", "Cover Body", [(colleges, None)]),
                               ("p", "Cover Body", [(cat.get("url", "iecc.edu/catalog"), None)])], 1, True))
    for f in parts["front"]:
        blocks = [("p", "Section Title", [(f["title"], None)])] + html_blocks(f["html"])
        sections.append((f["title"], blocks, 1, False))
    for s in parts["sections"]:
        head = [("p", "Kicker", [(f"Section {s['num']}", None)]), ("p", "Section Title", [(s["title"], None)])]
        if s["type"] == "courses":
            sections.append((s["title"], head + course_blocks(courses, prefixes), 2, False))
        else:
            sections.append((s["title"], head + html_blocks(s["html"]), 1, False))
    if parts.get("program_index"):
        sections.append(("Programs by Meta Major", [("p", "Section Title", [("Programs by Meta Major", None)])] + html_blocks(parts["program_index"]), 1, False))

    master_id, mpage, layer = ids(), ids(), "ulayer"
    head_story, foot_story = ids(), ids()
    stories: dict[str, str] = {}
    run_head = f"{cat['district']} · {cat['year']} Academic Catalog"
    stories[head_story] = story_xml(head_story, [("p", "Running Head", [(run_head, None)])], ids, width)
    stories[foot_story] = story_xml(foot_story, [("p", "Folio", [(ACE_PAGE, None)])], ids, width)
    rule_y = MARGIN["top"] - 18
    master = (HEAD + f'<idPkg:MasterSpread {NS}><MasterSpread Self="{master_id}" Name="A-Catalog" NamePrefix="A" BaseName="Catalog" '
              f'ShowMasterItems="true" PageCount="1" OverriddenPageItemProps="" PrimaryTextFrame="n" ItemTransform="1 0 0 1 0 0">'
              f'<Page Self="{mpage}" Name="A" AppliedMaster="n" OverrideList="" TabOrder="" GeometricBounds="0 0 {PAGE_H:g} {PAGE_W:g}" '
              f'ItemTransform="{PAGE_XFORM}" MasterPageTransform="1 0 0 1 0 0">{margin_pref()}</Page>'
              + text_frame(ids(), head_story, None, None, (FRAME[0], rule_y - 16, FRAME[2], rule_y - 3))
              + f'<GraphicLine Self="{ids()}" ItemLayer="{layer}" Visible="true" Name="$ID/" StrokeWeight="1.5" StrokeColor="Color/IECC Teal" '
                f'FillColor="Swatch/None" ItemTransform="{PAGE_XFORM}">{_rect_path(FRAME[0], rule_y, FRAME[2], rule_y, closed=False)}</GraphicLine>'
              + text_frame(ids(), foot_story, None, None, (FRAME[0], PAGE_H - 44, FRAME[2], PAGE_H - 30))
              + "</MasterSpread></idPkg:MasterSpread>")

    spreads: list[str] = []
    page_ids: list[str] = []
    report = []
    for title, blocks, cols, cover in sections:
        sid = ids()
        stories[sid] = story_xml(sid, blocks, ids, width)
        n = 1 if cover else estimate_pages(blocks, cols)
        report.append((title, n))
        frames = [ids() for _ in range(n)]
        for k in range(n):
            spid, pid = ids(), ids()
            page_ids.append(pid)
            pnum = len(page_ids)
            box = (FRAME[0], 180 if cover else FRAME[1], FRAME[2], FRAME[3])
            items = text_frame(frames[k], sid, frames[k - 1] if k else None, frames[k + 1] if k + 1 < n else None, box, cols)
            if cover:  # brand bar at the top of the cover
                items += (f'<Rectangle Self="{ids()}" ContentType="Unassigned" ItemLayer="{layer}" Visible="true" Name="$ID/" StrokeWeight="0" '
                          f'StrokeColor="Swatch/None" FillColor="Color/IECC Teal" ItemTransform="{PAGE_XFORM}">'
                          f'{_rect_path(FRAME[0], 54, FRAME[2], 66)}</Rectangle>')
            spreads.append(
                HEAD + f'<idPkg:Spread {NS}><Spread Self="{spid}" ShowMasterItems="true" PageCount="1" BindingLocation="0" SpreadHidden="false" '
                f'AllowPageShuffle="true" ItemTransform="1 0 0 1 0 {(pnum - 1) * (PAGE_H + 180):g}" FlattenerOverride="Default">'
                f'<Page Self="{pid}" Name="{pnum}" AppliedMaster="{"n" if cover else master_id}" OverrideList="" TabOrder="" '
                f'MasterPageTransform="1 0 0 1 0 0" GeometricBounds="0 0 {PAGE_H:g} {PAGE_W:g}" ItemTransform="{PAGE_XFORM}">{margin_pref()}</Page>'
                f'{items}</Spread></idPkg:Spread>')

    # assemble from the skeleton
    sk = SKELETON
    designmap = (sk / "designmap.xml").read_text(encoding="utf-8")
    layer_xml = (f'<Layer Self="{layer}" Name="Catalog" Visible="true" Locked="false" IgnoreWrap="false" ShowGuides="true" LockGuides="false" '
                 f'UI="true" Expendable="true" Printable="true"><Properties><LayerColor type="enumeration">LightBlue</LayerColor></Properties></Layer>')
    section_xml = (f'<Section Self="{ids()}" Length="{len(page_ids)}" Name="" ContinueNumbering="false" IncludeSectionPrefix="false" '
                   f'PageNumberStyle="Arabic" PageNumberStart="1" Marker="" PageStart="{page_ids[0]}" SectionPrefix=""/>')
    designmap = (designmap.replace("__STORYLIST__", " ".join(stories))
                 .replace("__LAYERS__", layer_xml)
                 .replace("__MASTERS__", f'<idPkg:MasterSpread src="MasterSpreads/MasterSpread_{master_id}.xml"/>')
                 .replace("__SPREADS__", "\n\t".join(f'<idPkg:Spread src="Spreads/Spread_{i:04d}.xml"/>' for i in range(len(spreads))))
                 .replace("__SECTION__", section_xml)
                 .replace("__STORIES__", "\n\t".join(f'<idPkg:Story src="Stories/Story_{s}.xml"/>' for s in stories)))
    para_xml, char_xml = styles_xml(fonts)
    styles = (sk / "Resources" / "Styles.xml").read_text(encoding="utf-8")
    styles = styles.replace("</RootParagraphStyleGroup>", para_xml + "</RootParagraphStyleGroup>", 1)
    styles = styles.replace("</RootCharacterStyleGroup>", char_xml + "</RootCharacterStyleGroup>", 1)
    graphic = (sk / "Resources" / "Graphic.xml").read_text(encoding="utf-8")
    graphic = re.sub(r"(<Color Self=\"Color/Black\")", colors_xml() + r"\1", graphic, count=1)
    prefs = (sk / "Resources" / "Preferences.xml").read_text(encoding="utf-8")
    prefs = re.sub(r"<MarginPreference [^>]*/>", margin_pref(), prefs, count=1)
    prefs = re.sub(r'LimitToMasterTextFrames="true"', 'LimitToMasterTextFrames="false"', prefs, count=1)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(out_path, "w") as z:
        z.writestr(zipfile.ZipInfo("mimetype"), "application/vnd.adobe.indesign-idml-package", compress_type=zipfile.ZIP_STORED)
        def put(name, data):
            z.writestr(name, data, compress_type=zipfile.ZIP_DEFLATED)
        put("META-INF/container.xml", (sk / "META-INF" / "container.xml").read_text(encoding="utf-8"))
        put("designmap.xml", designmap)
        put("Resources/Graphic.xml", graphic)
        put("Resources/Fonts.xml", (sk / "Resources" / "Fonts.xml").read_text(encoding="utf-8"))
        put("Resources/Styles.xml", styles)
        put("Resources/Preferences.xml", prefs)
        put("XML/Tags.xml", (sk / "XML" / "Tags.xml").read_text(encoding="utf-8"))
        put("XML/BackingStory.xml", (sk / "XML" / "BackingStory.xml").read_text(encoding="utf-8"))
        put(f"MasterSpreads/MasterSpread_{master_id}.xml", master)
        for i, s in enumerate(spreads):
            put(f"Spreads/Spread_{i:04d}.xml", s)
        for sid, xml in stories.items():
            put(f"Stories/Story_{sid}.xml", xml)
    jsx = out_path.parent / "Fit catalog pages.jsx"
    jsx.write_text(FIT_JSX, encoding="utf-8")
    return {"pages": len(page_ids), "sections": report, "stories": len(stories), "path": out_path, "script": jsx}


FIT_JSX = r"""// Fit catalog pages.jsx (written by catalog-builder)
// Run once after opening the catalog IDML in InDesign: Window > Utilities > Scripts, or File > Scripts > Browse...
// For every text story: adds pages (with a linked frame) until nothing is overset, then removes empty frames and pages.
#target indesign
(function () {
  if (!app.documents.length) { alert("Open the catalog first."); return; }
  var doc = app.activeDocument, added = 0, removed = 0;
  doc.viewPreferences.rulerOrigin = RulerOrigin.PAGE_ORIGIN;
  doc.recompose();
  var stories = doc.stories;
  for (var s = 0; s < stories.length; s++) {
    var st = stories[s], frames = st.textContainers;
    if (!frames.length) continue;
    var last = frames[frames.length - 1];
    if (!(last instanceof TextFrame) || !last.parentPage || last.parentPage.parent instanceof MasterSpread) continue;
    var guard = 0;
    while (last.overflows && guard++ < 400) {
      var pg = doc.pages.add(LocationOptions.AFTER, last.parentPage);
      pg.appliedMaster = last.parentPage.appliedMaster;
      var f = pg.textFrames.add({ geometricBounds: last.geometricBounds, itemLayer: last.itemLayer });
      f.textFramePreferences.textColumnCount = last.textFramePreferences.textColumnCount;
      f.textFramePreferences.textColumnGutter = last.textFramePreferences.textColumnGutter;
      last.nextTextFrame = f; last = f; added++;
      doc.recompose();
    }
    // remove empty trailing frames (and their pages, when nothing else is on them)
    frames = st.textContainers;
    for (var k = frames.length - 1; k > 0; k--) {
      var fr = frames[k];
      if (fr.characters.length > 0) break;
      var p = fr.parentPage; fr.remove(); removed++;
      if (p && p.pageItems.length === 0 && doc.pages.length > 1) p.remove();
    }
  }
  alert("Catalog pages fitted.\nPages added: " + added + "\nEmpty frames removed: " + removed);
})();
"""
