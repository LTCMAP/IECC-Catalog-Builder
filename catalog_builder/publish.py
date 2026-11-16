"""Publish folder for the web (GitHub Pages, IIS, or Drupal's public files):

  <site>/index.html            sends visitors to current/
  <site>/catalog-years.js      year list for every edition's switcher
  <site>/current/              the live catalog, rebuilt every run
  <site>/2026-27/              edition of record, written once with --freeze, never rebuilt
  <site>/2026-27/snapshot.json   course data as frozen (used to draft addenda)
  <site>/2026-27/addenda.js      approved addenda (from content/addenda/2026-27.csv; the only file that changes later)
  <site>/feeds/courses.csv, programs.csv, addenda.csv   for Drupal Feeds (one row per item per catalog year)

Board Policy 500.36: students follow the catalog for the year they entered, so editions of record never change;
later changes reach them as numbered, dated addenda.
"""
from __future__ import annotations

import csv
import json
import re
import shutil
from pathlib import Path

from .book import slug as _slug
from .digital import _year_slug, build_site, write_years_js
from .outputs import diff_snapshots, subject_name

COURSE_COLS = ["guid", "catalog_year", "code", "prefix", "number", "subject", "title", "credits", "variable", "delivery",
               "repeatable", "campuses", "iai", "prerequisite", "corequisite", "description", "url"]
PROGRAM_COLS = ["guid", "catalog_year", "code", "title", "award", "type", "meta_major", "department", "campuses", "url", "page"]
ADDENDA_COLS = ["guid", "catalog_year", "number", "effective", "title", "summary", "pdf"]


def _addenda(content_dir: Path, slug: str) -> list[dict]:
    f = content_dir / "addenda" / f"{slug}.csv"
    if not f.exists():
        return []
    with f.open(encoding="utf-8-sig") as fh:
        return [r for r in csv.DictReader(fh) if (r.get("approved", "").strip().lower() in ("yes", "y", "true", "1"))]


def _write_addenda_js(folder: Path, rows: list[dict]):
    keep = [{k: r.get(k, "") for k in ("number", "effective", "title", "summary", "pdf")} for r in rows]
    (folder / "addenda.js").write_text("window.IECC_ADDENDA=" + json.dumps(keep, ensure_ascii=False, indent=1) + ";\n", encoding="utf-8")


def publish(courses, prefixes, parts: dict, content_dir: Path, site: Path, *, built: str, pdf: Path | None = None,
            freeze: bool = False, base_url: str = "", preview: bool = False) -> dict:
    site.mkdir(parents=True, exist_ok=True)
    cat = parts["cat"]
    slug = _year_slug(cat["year"])
    frozen_dir = site / slug
    result = {"slug": slug, "frozen_now": False, "draft": None, "notes": []}

    # 1. freeze the edition of record (once)
    if freeze:
        if (frozen_dir / "index.html").exists():
            result["notes"].append(("warning", "Edition already frozen", slug,
                                    f"{slug}/ already exists, so it was left untouched. Changes for {cat['year']} go out as addenda."))
        else:
            build_site(courses, prefixes, parts, frozen_dir, kind="frozen", built=built, pdf=pdf)
            (frozen_dir / "snapshot.json").write_text(json.dumps([c.to_public() for c in courses], indent=1, ensure_ascii=False), encoding="utf-8")
            result["frozen_now"] = True

    # 2. the current catalog (always rebuilt); points at the newest edition of record
    editions = sorted((d.name for d in site.iterdir() if d.is_dir() and re.fullmatch(r"\d{4}-\d{2}", d.name)), reverse=True)
    cur = site / "current"
    if cur.exists():
        shutil.rmtree(cur)
    build_site(courses, prefixes, parts, cur, kind="current", built=built, pdf=pdf, record=editions[0] if editions else "")

    # 3. addenda: approved rows -> each edition's addenda.js (the one file a frozen edition may gain)
    all_add = []
    for ed in editions:
        rows = _addenda(content_dir, ed)
        _write_addenda_js(site / ed, rows)
        all_add += [dict(r, catalog_year=ed, guid=f"{ed}:{r.get('number', '')}") for r in rows]
    _write_addenda_js(cur, [r for r in all_add if r["catalog_year"] == (editions[0] if editions else "")])

    # 4. draft addenda: what changed in FileMaker since the edition of record was frozen
    snap = frozen_dir / "snapshot.json"
    if snap.exists():
        d = diff_snapshots(json.loads(snap.read_text(encoding="utf-8")), [c.to_public() for c in courses])
        result["draft"] = d
        n = len(d["added"]) + len(d["removed"]) + len(d["changed"])
        if n:
            result["notes"].append(("info", "Changes since edition of record", slug,
                                    f"{n} course change(s) since {slug} was frozen (+{len(d['added'])} / -{len(d['removed'])} / ~{len(d['changed'])}). "
                                    f"They show in current/ now. To tell {slug} students, approve an addendum in content/addenda/{slug}.csv."))

    # 5. Drupal feeds
    feeds = site / "feeds"
    feeds.mkdir(exist_ok=True)
    base = base_url.rstrip("/")
    year_key = editions[0] if editions else slug
    with (feeds / "courses.csv").open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=COURSE_COLS); w.writeheader()
        for c in courses:
            p = c.to_public()
            w.writerow({**{k: p.get(k, "") for k in COURSE_COLS}, "guid": f"{year_key}:{c.code}", "catalog_year": year_key,
                        "subject": subject_name(c.prefix, prefixes), "campuses": " ".join(p["campuses"]), "iai": " ".join(p["iai"]),
                        "url": f"{base}/current/courses.html#c-{c.prefix}{c.number}"})
    reg = content_dir / "programs" / "program-registry.csv"
    built_pages = {}
    for f in sorted((content_dir / "programs").glob("*.json")):
        pj = json.loads(f.read_text(encoding="utf-8"))
        built_pages[pj["code"].split()[-1]] = f"prog-{_slug(pj['code'] + ' ' + pj['title'])}"
    with (feeds / "programs.csv").open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=PROGRAM_COLS); w.writeheader()
        if reg.exists():
            with reg.open(encoding="utf-8") as rf:
                for r in csv.DictReader(rf):
                    anchor = built_pages.get(r["code"])
                    w.writerow({**{k: r.get(k, "") for k in PROGRAM_COLS}, "guid": f"{year_key}:{r['code']}", "catalog_year": year_key,
                                "page": f"{base}/current/programs.html" + (f"#{anchor}" if anchor else "")})
    with (feeds / "addenda.csv").open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=ADDENDA_COLS, extrasaction="ignore"); w.writeheader(); w.writerows(all_add)

    # 6. root: year list + redirect
    years = write_years_js(site)
    (site / "index.html").write_text('<!doctype html><meta charset="utf-8"><title>Academic Catalog</title>'
                                     '<meta http-equiv="refresh" content="0; url=current/"><link rel="canonical" href="current/">'
                                     '<a href="current/">Go to the current Academic Catalog</a>', encoding="utf-8")
    _web_config(site, preview)
    result["years"] = [y["slug"] for y in years]
    return result


WEB_CONFIG = """<?xml version="1.0" encoding="utf-8"?>
<!-- Written by catalog-builder for IIS (vm-webserver). Safe to re-write on every run. -->
<configuration>
  <system.webServer>
    <defaultDocument enabled="true">
      <files><clear /><add value="index.html" /></files>
    </defaultDocument>
    <staticContent>
      <remove fileExtension=".woff2" /><mimeMap fileExtension=".woff2" mimeType="font/woff2" />
      <remove fileExtension=".csv" /><mimeMap fileExtension=".csv" mimeType="text/csv; charset=utf-8" />
      <remove fileExtension=".json" /><mimeMap fileExtension=".json" mimeType="application/json" />
      <clientCache cacheControlMode="UseMaxAge" cacheControlMaxAge="0.01:00:00" />
    </staticContent>
    <httpProtocol>
      <customHeaders>
        <remove name="X-Robots-Tag" />
__ROBOTS__
      </customHeaders>
    </httpProtocol>
  </system.webServer>
</configuration>
"""


def _web_config(site: Path, preview: bool):
    """IIS settings: index.html as the default page, font/CSV MIME types, and (while previewing) keep search engines out."""
    robots = '        <add name="X-Robots-Tag" value="noindex, nofollow" />' if preview else ""
    (site / "web.config").write_text(WEB_CONFIG.replace("__ROBOTS__", robots), encoding="utf-8")
