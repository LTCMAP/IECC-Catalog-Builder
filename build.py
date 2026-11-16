#!/usr/bin/env python3
"""
IECC catalog-builder
--------------------
Reads the FileMaker course export (FMPXMLRESULT .xml) and builds:

  out/indesign/<PREFIX>.txt     InDesign Tagged Text, one file per subject (place + link these)
  out/print/*.pdf               Designed course-description section (preview / proof)
  out/web/course-descriptions.html   Searchable, accessible web version
  out/data/courses.json|csv     Clean data (for Drupal Feeds, etc.)
  out/report.html               Data checks + changes since the last build (= addendum draft)

Usage:
  python build.py                         # uses config.json next to this file
  python build.py --export X.xml --out OUT
  python build.py --only-if-changed       # for Task Scheduler: exits quietly if the export hasn't changed
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime
from pathlib import Path

HERE = Path(getattr(sys, "_MEIPASS", Path(__file__).parent))  # works when frozen with PyInstaller
APP_DIR = Path(sys.executable).parent if getattr(sys, "frozen", False) else Path(__file__).parent
sys.path.insert(0, str(HERE))

from catalog_builder.model import load_export            # noqa: E402
from catalog_builder.checks import run_checks             # noqa: E402
from catalog_builder.outputs import write_tagged_text, write_data, write_print, diff_snapshots  # noqa: E402
from catalog_builder.web import write_web                 # noqa: E402
from catalog_builder.report import write_report           # noqa: E402
from catalog_builder.checks import Finding                # noqa: E402


def main() -> int:
    cfg_path = APP_DIR / "config.json"
    cfg = json.loads(cfg_path.read_text()) if cfg_path.exists() else {}
    ap = argparse.ArgumentParser(description="Build IECC catalog outputs from a FileMaker export.")
    ap.add_argument("--export", default=cfg.get("export"), help="Path to the FileMaker XML export")
    ap.add_argument("--out", default=cfg.get("out", "out"), help="Output folder (can be a network share)")
    ap.add_argument("--only-if-changed", action="store_true", help="Skip the build if the export is unchanged")
    ap.add_argument("--no-pdf", action="store_true", help="Skip the PDF proof (faster)")
    ap.add_argument("--content", default=cfg.get("content", str(HERE / "content")), help="Folder with catalog.json, sections/, calendar.csv, programs/")
    ap.add_argument("--no-book", action="store_true", help="Skip the full-catalog PDF")
    ap.add_argument("--update-trustees", action="store_true", help="Copy the trustees list from iecc.edu into content/board.json")
    ap.add_argument("--no-web-checks", action="store_true", help="Skip checking iecc.edu (offline or test runs)")
    ap.add_argument("--site", default=cfg.get("site"), help="Publish folder for the digital catalog + Drupal feeds (e.g. a network share or Git repo)")
    ap.add_argument("--freeze", action="store_true", help="Also write this year's edition of record (once; never overwritten)")
    ap.add_argument("--site-url", default=cfg.get("site_url", ""), help="Public URL of the publish folder, used in feed links")
    ap.add_argument("--preview", action="store_true", default=bool(cfg.get("preview", False)), help="Tell search engines not to index the published site (draft/proofing)")
    ap.add_argument("--sample", default=cfg.get("sample_prefixes", "ACC,LSC,WEL"), help="Prefixes for the short sample PDF")
    a = ap.parse_args()
    if not a.export:
        ap.error("No export given (use --export or config.json)")

    export = Path(a.export)
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    state_file = out / ".last_build.json"
    content = Path(a.content)
    trustee_findings = []
    # Board of Trustees: compare content/board.json with the live iecc.edu page
    if not a.no_web_checks and (content / "catalog.json").exists():
        from catalog_builder.trustees import check as check_trustees, DEFAULT_URL
        _url = json.loads((content / "catalog.json").read_text(encoding="utf-8")).get("trustees_url", DEFAULT_URL)
        _tr = check_trustees(content, _url, update=a.update_trustees)
        for sev, rule, code, msg in _tr:
            trustee_findings.append((sev, rule, code, msg))
        print("Trustees: " + ("matches iecc.edu" if not _tr else f"{len(_tr)} item(s) to review (see report)"))


    # Rebuild when the export, the template content, or the trustee check result changes
    h = hashlib.sha256(export.read_bytes())
    if content.exists():
        for f in sorted(p for p in content.rglob("*") if p.is_file()):
            h.update(str(f.relative_to(content)).encode()); h.update(f.read_bytes())
    h.update(json.dumps(trustee_findings).encode())
    digest = h.hexdigest()
    state = json.loads(state_file.read_text()) if state_file.exists() else {}
    if a.only_if_changed and state.get("sha256") == digest:
        print("Export, content and trustees unchanged since last build. Nothing to do.")
        return 0

    built_at = datetime.now().strftime("%B %d, %Y %I:%M %p").replace(" 0", " ")
    cfgdir = HERE / "config"
    prefixes = json.loads((cfgdir / "prefixes.json").read_text(encoding="utf-8"))
    # Optional, kept OUT of the repo: internal comparison against the printed catalog
    cmp_path = cfg.get("print_comparison")
    cmp_file = (APP_DIR / cmp_path) if cmp_path else None
    print_cmp = json.loads(cmp_file.read_text(encoding="utf-8")) if cmp_file and cmp_file.exists() else None

    courses, meta = load_export(str(export))
    print(f"Loaded {len(courses)} courses from {export.name}")
    findings = run_checks(courses, meta, prefixes, print_cmp)
    findings += [Finding(*t) for t in trustee_findings]

    # Change detection against the previous snapshot
    snaps = out / "snapshots"
    snaps.mkdir(exist_ok=True)
    latest = snaps / "latest.json"
    new_snap = [c.to_public() for c in courses]
    changes = diff_snapshots(json.loads(latest.read_text(encoding="utf-8")), new_snap) if latest.exists() else None

    tt = write_tagged_text(courses, prefixes, out / "indesign")
    data = write_data(courses, prefixes, out / "data")
    web = write_web(courses, prefixes, out / "web", built_at)
    pdfs = []
    if not a.no_pdf:
        try:
            pdfs = write_print(courses, prefixes, out / "print", [p.strip() for p in a.sample.split(",") if p.strip()])
        except (ImportError, OSError) as e:
            print(f"PDF proof skipped (WeasyPrint not available: {e.__class__.__name__}). Everything else was built.")
    # Full catalog (template + FileMaker data)
    if not a.no_pdf and not a.no_book and (content / "catalog.json").exists():
        try:
            from catalog_builder.book import write_book
            logo = next((p for p in [APP_DIR / "logo.svg", APP_DIR / "logo.png", HERE / "content" / "logo.svg", HERE / "content" / "logo.png"] if p.exists()), None)
            book, bstats = write_book(courses, prefixes, content, out / "print", logo)
            pdfs.append(book)
            for sev, rule, code, msg in bstats["issues"]:
                findings.append(Finding(sev, rule, code, msg))
            for f, n in bstats["todos"].items():
                if n:
                    findings.append(Finding("info", "Template placeholders left", f, f"{n} placeholder(s) still to fill in."))
        except (ImportError, OSError) as e:
            print(f"Full catalog skipped (WeasyPrint not available: {e.__class__.__name__}).")

    # Digital catalog (website) + Drupal feeds
    site_result = None
    if (content / "catalog.json").exists():
        from catalog_builder.book import build_book_html
        from catalog_builder.digital import build_site
        _, wstats = build_book_html(courses, prefixes, content)
        full_pdf = out / "print" / "full-catalog.pdf"
        full_pdf = full_pdf if full_pdf.exists() else None
        build_site(courses, prefixes, wstats["parts"], out / "digital", kind="current", built=" ".join(built_at.split(" ")[:3]), pdf=full_pdf)
        if a.site:
            from catalog_builder.publish import publish
            site_result = publish(courses, prefixes, wstats["parts"], content, Path(a.site), built=" ".join(built_at.split(" ")[:3]),
                                  pdf=full_pdf, freeze=a.freeze, base_url=a.site_url, preview=a.preview)
            for sev, rule, code, msg in site_result["notes"]:
                findings.append(Finding(sev, rule, code, msg))

    rpt = write_report(out / "report.html", findings=findings, changes=changes, meta=meta, n_courses=len(courses),
                       built_at=built_at, export_name=export.name)

    stamp = datetime.now().strftime("%Y-%m-%d_%H%M")
    snap_json = json.dumps(new_snap, indent=1, ensure_ascii=False)
    (snaps / f"{stamp}.json").write_text(snap_json, encoding="utf-8")
    latest.write_text(snap_json, encoding="utf-8")
    state_file.write_text(json.dumps({"sha256": digest, "built_at": built_at}))

    errs = sum(f.severity == "error" for f in findings)
    warns = sum(f.severity == "warning" for f in findings)
    print(f"InDesign files: {len(tt)} · PDFs: {len(pdfs)} · web: {web.name} · report: {rpt}")
    print(f"Checks: {errs} errors, {warns} warnings")
    print(f"Digital catalog: {out / 'digital' / 'index.html'}" + (f" · published to {a.site} ({', '.join(site_result['years'])})" if site_result else ""))
    if changes:
        print(f"Changes since last build: +{len(changes['added'])} / -{len(changes['removed'])} / ~{len(changes['changed'])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
