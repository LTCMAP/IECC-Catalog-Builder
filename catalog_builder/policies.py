"""Board policy register: content/policies/policy-register.csv + content/policies/<number>.md.

In any section markdown file:
  {{policy 500.4}}        -> inserts the policy's current text, with a source/date line
  {{policy-ref 500.4}}    -> inline mention: "Course Repeat Policy (Board Policy 500.4)"
"""
from __future__ import annotations

import csv
import re
from pathlib import Path

BLOCK = re.compile(r"^\{\{policy\s+(\d{3}\.\d+)\}\}\s*$", re.M)
INLINE = re.compile(r"\{\{policy-ref\s+(\d{3}\.\d+)\}\}")


def _fmt(iso: str) -> str:
    if not iso:
        return ""
    y, m, d = iso.split("-")
    return f"{int(m)}/{int(d)}/{y}"


def load_register(content_dir: Path) -> dict:
    reg_file = content_dir / "policies" / "policy-register.csv"
    if not reg_file.exists():
        return {}
    with reg_file.open(encoding="utf-8") as fh:
        return {r["number"]: r for r in csv.DictReader(fh)}


def _body(content_dir: Path, rec: dict) -> str:
    f = content_dir / rec.get("file", "")
    if not rec.get("file") or not f.exists():
        return ""
    text = f.read_text(encoding="utf-8")
    text = re.sub(r"^---\n.*?\n---\n", "", text, flags=re.S)
    text = re.sub(r"^# .*\n", "", text.lstrip(), count=1)
    # demote any headings so they sit under the section's ## heading
    return re.sub(r"^(#{1,4}) ", lambda m: "#" * min(len(m.group(1)) + 2, 6) + " ", text, flags=re.M).strip()


def expand(text: str, content_dir: Path, reg: dict, issues: list, where: str) -> str:
    def block(m):
        num = m.group(1)
        rec = reg.get(num)
        if not rec:
            issues.append(("error", "Policy not in register", num, f"{where} references Board Policy {num}, which isn't in policy-register.csv."))
            return f"TODO: Board Policy {num} not found in the policy register."
        if rec.get("status") == "deleted":
            issues.append(("error", "Deleted policy referenced", num, f"{where} includes Board Policy {num} ({rec['title']}), which the Board has deleted."))
        body = _body(content_dir, rec)
        if not body:
            issues.append(("warning", "Policy text missing", num, f"{where}: no text file for Board Policy {num}."))
            body = f"TODO: Add the text of Board Policy {num}."
        rev = rec.get("last_revised") or rec.get("text_revised")
        src = f"> Board Policy {num} · Adopted {_fmt(rec.get('adopted', ''))}" + (f" · Last revised {_fmt(rev)}" if rev else "") + " · Full policy manual: iecc.edu/policymanual"
        return body + "\n\n" + src

    def inline(m):
        rec = reg.get(m.group(1))
        if not rec:
            issues.append(("error", "Policy not in register", m.group(1), f"{where} mentions Board Policy {m.group(1)}, which isn't in the register."))
            return f"Board Policy {m.group(1)}"
        return f"{rec['title']} (Board Policy {m.group(1)})"

    return INLINE.sub(inline, BLOCK.sub(block, text))


def register_issues(reg: dict, since: str = "") -> list:
    """Register-level checks: contents vs. policy text dates, and policies revised after `since` (YYYY-MM-DD)."""
    out = []
    for num, r in reg.items():
        if r.get("status") != "deleted" and r.get("last_revised") and r.get("text_revised") and r["last_revised"] != r["text_revised"]:
            out.append(("warning", "Policy dates disagree", num, f"{r['title']}: the manual's contents page says last revised {_fmt(r['last_revised'])}, the policy text says {_fmt(r['text_revised'])}."))
        if r.get("in_contents") == "NO":
            out.append(("warning", "Policy missing from contents", num, f"{r['title']} is in the policy PDF but not on the manual's contents page."))
        rev = max(r.get("last_revised", ""), r.get("text_revised", ""))
        if since and rev and rev > since:
            out.append(("info", "Policy revised since last catalog", num, f"{r['title']} was revised {_fmt(rev)}. Check any catalog text that summarizes it."))
    return out
