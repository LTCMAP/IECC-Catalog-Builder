# IECC catalog-builder

Turns the FileMaker course export, plus the catalog's own content folder, into every version of the IECC Academic Catalog:

| Output | Where | Used for |
|---|---|---|
| **InDesign IDML** (full catalog) | `output/indesign/IECC-Academic-Catalog-<year>.idml` + `Fit catalog pages.jsx` | Marketing's starting document: every section, program table and course, all on named paragraph/character styles. |
| InDesign Tagged Text | `output/indesign/<PREFIX>.txt` + `_ALL-COURSES.txt` | Place **linked** in an InDesign document; the Links panel flags changes, and Update pulls them in. |
| Full catalog PDF | `output/print/full-catalog.pdf` | Tagged PDF/UA proof of the whole catalog (brand template). |
| Digital catalog | `output/digital/` and, with `site`, `site/current/` + `site/<year>/` | Searchable website: **current** (rebuilt every run) and **frozen editions of record** (Board Policy 500.36). |
| Drupal feeds | `site/feeds/*.csv` | Courses, programs and addenda for Drupal Feeds (`docs/DRUPAL-SETUP.md`). |
| Report | `output/report.html` | Data checks, trustee/policy checks, and **what changed since the last build** (the addendum draft). |

Nothing is published unless `site` is set, and frozen editions are never overwritten.

**Setting it up:** `deploy/LOCAL-TEST.md` (one PC, test folder) → `deploy/SERVER-SETUP.md` (FileMaker Server + scheduled task).

---

## Running it

Windows (download from Releases): put `config.json` next to `catalog-builder.exe` and double-click `run-catalog-build.bat`, or run `catalog-builder.exe` from a command prompt.

From source: Python 3.10+, `pip install -r requirements.txt`, then `python build.py`.

| Option | What it does |
|---|---|
| `--freeze` | Also writes this year's **edition of record** (`site/2026-27/`). Once per catalog year. |
| `--only-if-changed` | Exits right away if the export, content and trustee list are unchanged (scheduled runs). |
| `--no-pdf` / `--no-book` / `--no-idml` | Skip the PDFs / the full-catalog PDF / the IDML. |
| `--update-trustees` | Copy the Board of Trustees from iecc.edu into `content/board.json`. |
| `--no-web-checks` | Don't check iecc.edu (offline runs). |

## config.json

```json
{
  "export": "..\\exports\\courses.xml",
  "content": "content",
  "out": "..\\output",
  "marketing_folder": "..\\marketing",
  "site": "..\\site",
  "site_url": "https://my.iecc.edu/catalog",
  "preview": true,
  "indesign_fonts": {
    "sans":  {"family": "Futura PT", "regular": "Book", "medium": "Medium", "semibold": "Medium", "bold": "Bold", "italic": "Book Oblique"},
    "serif": {"family": "EB Garamond", "regular": "Regular", "medium": "Medium", "semibold": "SemiBold", "bold": "Bold", "italic": "Italic"}
  }
}
```

- Relative paths are relative to the folder holding the exe. In JSON, write each `\` as `\\`.
- `marketing_folder`: after each build, the IDML, the page-fitting script, the full PDF and the report are copied here.
- `indesign_fonts` is optional; the values above are the defaults (the brand fonts). Each style weight maps to a font style name.
- `weasyprint`: optional path to a `weasyprint.exe` if it isn't in the `weasyprint` folder next to the builder.

## The IDML

- Letter pages, one parent page (A-Catalog: running head, teal rule, page number), one story per section, each starting on a new page. Course Descriptions is two columns.
- **Paragraph styles:** Section Title, Kicker, Heading 2–4, Body, Lede, Bullet, Numbered, Source Note, Placeholder, Program Title, Program Meta, Program Description, Term Head, Program Total, Table Head, Table Body, Table Credits, Subject Head, Course Head, Course Meta, Course Description, Course Requisite, Running Head, Folio, Cover styles.
- **Character styles:** Course Code, Credits, Campus FCC/LTC/OCC/WVC, IAI, Requisite Label, Bold, Italic, Superscript, Or, Missing.
- **Swatches:** IECC Teal, FCC Gold, LTC Green, OCC Navy, WVC Red, Catalog Ink, Catalog Gray.
- Page counts are estimates. Run **Fit catalog pages.jsx** once after opening (it adds pages for overset text and removes empty ones).
- The Tagged Text files use the same course style names, so the IDML and the linked text files can be mixed.

## Content folder (`content/`)

`catalog.json` (year, colleges, section list) · `sections/*.md` (section text; `{{policy 500.4}}` pulls a Board policy) · `calendar.csv` · `programs/` (registry + program requirement files) · `policies/` (Board Policy Manual register) · `board.json` (trustees, checked against iecc.edu every build) · `addenda/<year>.csv` (approved addenda).

## Checks performed

Errors: missing descriptions, placeholder text, duplicate or invalid codes, trustee list differs from iecc.edu, deleted policies referenced.
Warnings: non-standard requisite labels, broken apostrophes (`Labor?s`), courses referenced but not in the export, lecture + lab ≠ credit hours, unknown prefixes, policy date mismatches, programs missing from meta majors.
Notes: auto-cleaned spacing and characters, policies revised since the catalog was reviewed.

## Files

```
build.py                       entry point
config/prefixes.json           prefix → subject name
catalog_builder/model.py       reads the FileMaker XML, splits out prerequisites
catalog_builder/checks.py      data-quality rules
catalog_builder/outputs.py     tagged text, data files, course PDF, change detection
catalog_builder/book.py        full catalog (template + data) → HTML/PDF
catalog_builder/idml.py        full catalog → InDesign IDML (+ page-fitting script)
catalog_builder/digital.py     digital catalog website
catalog_builder/publish.py     current / frozen editions, addenda, Drupal feeds, IIS web.config
catalog_builder/pdfrender.py   PDF via WeasyPrint (Python package or bundled weasyprint.exe)
catalog_builder/policies.py    Board policy register
catalog_builder/trustees.py    Board of Trustees check
catalog_builder/assets/        CSS, JS, fonts (Jost, EB Garamond: SIL OFL), IDML skeleton
deploy/                        LOCAL-TEST.md, SERVER-SETUP.md, server config, scheduled task
docs/DRUPAL-SETUP.md           Drupal content types + Feeds mapping
tools/import_policies.py       rebuild content/policies from the Policy Manual PDFs
```
