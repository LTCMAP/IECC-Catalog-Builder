"""Board of Trustees: content/board.json is what prints; the live iecc.edu page is checked on every build.

In a section file, a line containing only {{trustees}} prints the board table from board.json.
Each build fetches the trustees page (catalog.json "trustees_url") and reports any difference:
someone added or removed, a changed role or hometown, or new officers.
Run build.py with --update-trustees to copy the website's list into board.json.
"""
from __future__ import annotations

import html
import json
import re
import urllib.request
from pathlib import Path

DEFAULT_URL = "https://iecc.edu/iecc/about-employment/iecc-district/board-trustees"
CARD = re.compile(r'class="card-label"[^>]*>(.*?)</div>.*?class="card-title"[^>]*>(.*?)</div>', re.S)
OFFICERS = re.compile(r"([A-Z][\w.'-]+(?: [A-Z][\w.'-]+)+) currently serves as the Board Treasurer and ([A-Z][\w.'-]+(?: [A-Z][\w.'-]+)+) as the Board Secretary")


def _txt(s: str) -> str:
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", "", s))).strip()


def parse_page(page: str) -> dict:
    members = []
    for label, title in CARD.findall(page):
        label, title = _txt(label), _txt(title)
        if "," not in label:
            continue
        name, role = [x.strip() for x in label.split(",", 1)]
        place = title.split(",", 1)[1].strip() if "," in title else ""
        members.append({"name": name, "role": role, "place": place})
    off = OFFICERS.search(_txt(page))
    officers = {"treasurer": off.group(1).split(". ")[-1], "secretary": off.group(2).split(". ")[-1]} if off else {}
    return {"members": members, "officers": officers}


def fetch(url: str, timeout: int = 20) -> dict:
    req = urllib.request.Request(url, headers={"User-Agent": "IECC-Catalog-Builder (+https://github.com/LTCMAP/IECC-Catalog-Builder)"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return parse_page(r.read().decode("utf-8", "replace"))


def load(content_dir: Path) -> dict:
    f = content_dir / "board.json"
    return json.loads(f.read_text(encoding="utf-8")) if f.exists() else {"members": [], "officers": {}}


def compare(saved: dict, live: dict) -> list:
    """Return issues tuples (severity, rule, code, message)."""
    out = []
    key = lambda m: re.sub(r"^(dr|mr|mrs|ms)\.?\s+", "", m["name"].lower())
    s = {key(m): m for m in saved.get("members", [])}
    w = {key(m): m for m in live.get("members", [])}
    for k in w.keys() - s.keys():
        out.append(("error", "Trustees changed on website", w[k]["name"], f"{w[k]['name']} ({w[k]['role']}) is on iecc.edu but not in content/board.json."))
    for k in s.keys() - w.keys():
        out.append(("error", "Trustees changed on website", s[k]["name"], f"{s[k]['name']} is in content/board.json but no longer on iecc.edu."))
    for k in s.keys() & w.keys():
        for f in ("role", "place"):
            if s[k].get(f, "") != w[k].get(f, ""):
                out.append(("error", "Trustees changed on website", s[k]["name"], f"{f.title()}: catalog has “{s[k].get(f, '')}”, website has “{w[k].get(f, '')}”."))
    if live.get("officers") and live["officers"] != saved.get("officers", {}):
        out.append(("error", "Trustees changed on website", "Officers", f"Website lists Treasurer {live['officers'].get('treasurer')} and Secretary {live['officers'].get('secretary')}; board.json has {saved.get('officers') or 'none'}."))
    if live.get("members") is not None and not live["members"]:
        out.append(("warning", "Trustee check failed", "website", "The trustees page loaded but no trustee cards were found. The page layout may have changed; check it by hand."))
    return out


def check(content_dir: Path, url: str, update: bool = False) -> list:
    saved = load(content_dir)
    try:
        live = fetch(url)
    except Exception as e:  # offline, blocked, timeout
        return [("warning", "Trustee check failed", "website", f"Couldn't reach {url} ({e.__class__.__name__}). Check the Board of Trustees by hand before publishing.")]
    if update and live["members"]:
        (content_dir / "board.json").write_text(json.dumps(live, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        return [("info", "Trustees updated from website", "board.json", f"Copied {len(live['members'])} trustees from iecc.edu into content/board.json.")]
    return compare(saved, live)


def expand(text: str, content_dir: Path) -> str:
    if "{{trustees}}" not in text:
        return text
    b = load(content_dir)
    rows = ["| Name | Position | Hometown / College |", "|---|---|---|"]
    rows += [f"| {m['name']} | {m['role']} | {m['place']} |" for m in b.get("members", [])]
    o = b.get("officers") or {}
    if o:
        rows += ["", f"{o.get('treasurer', '')}, Board Treasurer · {o.get('secretary', '')}, Board Secretary and Ethics Officer"]
    return re.sub(r"^\{\{trustees\}\}\s*$", "\n".join(rows), text, flags=re.M)
