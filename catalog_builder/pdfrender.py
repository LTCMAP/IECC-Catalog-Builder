"""HTML -> tagged PDF (PDF/UA-1) with WeasyPrint.

Uses the WeasyPrint Python package when it's installed (Mac/dev runs). The Windows exe instead calls
the official standalone weasyprint.exe that ships next to it in the download (weasyprint\\weasyprint.exe),
so no Python, GTK or installs are needed on the server. Set "weasyprint" in config.json to point somewhere else.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

_EXE: Path | None = None


def _app_dir() -> Path:
    return Path(sys.executable).parent if getattr(sys, "frozen", False) else Path(__file__).resolve().parent.parent


def find_exe(configured: str | None = None) -> Path | None:
    cands = []
    if configured:
        cands.append(Path(configured))
    if os.environ.get("WEASYPRINT_EXE"):
        cands.append(Path(os.environ["WEASYPRINT_EXE"]))
    app = _app_dir()
    cands += list(app.glob("weasyprint/**/weasyprint.exe")) + [app / "weasyprint.exe"]
    w = shutil.which("weasyprint")
    if w:
        cands.append(Path(w))
    return next((c for c in cands if c.exists()), None)


def configure(path: str | None):
    global _EXE
    _EXE = find_exe(path)


def available() -> str:
    try:
        import weasyprint  # noqa: F401
        return "python"
    except (ImportError, OSError):
        pass
    return "exe" if (_EXE or find_exe()) else ""


def render(doc: str, out_pdf: Path, base_url: str | Path) -> Path:
    """Write doc (a full HTML string) to out_pdf. Raises ImportError if no WeasyPrint is available."""
    out_pdf.parent.mkdir(parents=True, exist_ok=True)
    try:
        from weasyprint import HTML
        HTML(string=doc, base_url=str(base_url)).write_pdf(out_pdf, pdf_variant="pdf/ua-1")
        return out_pdf
    except (ImportError, OSError):
        pass
    exe = _EXE or find_exe()
    if not exe:
        raise ImportError("WeasyPrint not found (no Python package and no weasyprint.exe next to catalog-builder.exe)")
    src = out_pdf.with_suffix(".source.html")
    src.write_text(doc, encoding="utf-8")
    try:
        base = Path(base_url).resolve().as_uri().rstrip("/") + "/"
        r = subprocess.run([str(exe), "--pdf-variant", "pdf/ua-1", "--base-url", base, str(src), str(out_pdf)],
                           capture_output=True, text=True, timeout=1800)
        if r.returncode != 0 or not out_pdf.exists():
            raise OSError(f"weasyprint.exe failed ({r.returncode}): {(r.stderr or r.stdout)[-400:]}")
    finally:
        try:
            src.unlink()
        except OSError:
            pass
    return out_pdf
