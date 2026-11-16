# Catalog content (edit these files)

Everything in the catalog that **doesn't** come from FileMaker lives here. Edit, re-run the builder, and the PDF, contents page, and page numbers update themselves.

| File | What it is | How to edit |
|---|---|---|
| `catalog.json` | Catalog year, college contact info, and the **order of sections** | Change `"year"` each cycle. Reorder/rename sections here. |
| `sections/*.md` | Policy & narrative text (one file per section) | Plain text. `## Heading` makes a sub-heading **and** a contents entry. `- item` makes bullets, `1. item` numbered lists, `**bold**`, `> note` a callout, and `\| a \| b \|` rows a table. |
| `calendar.csv` | Academic calendar | Open in Excel. One row per date: term, month, days, event. |
| `programs/*.json` | Degree & certificate pages | List **course codes only**. Titles and credits fill in from FileMaker, and totals are checked automatically. Copy `business-administration-aas.json` to start a new one. |

**Placeholders:** any line starting with `TODO:` prints as a teal dashed box and is counted in `report.html`, so you always know what's left before publishing.

**Logo:** drop `logo.svg` or `logo.png` into this folder (or next to `build.py`) and it appears on the cover.

## Program list (`programs/program-registry.csv`)

The master list of all programs (code, title, type, **meta major**, department, pathway, campuses, web page), taken from **my.iecc.edu/metamajors**, plus the 2026–27 catalog programs that aren't on that site yet. It drives the **Programs by Meta Major** index. A program with a full page in `programs/*.json` is matched by its code (e.g. `BUS D186` → `D186`) and gets its page number and meta major automatically.

When programs are formally added to FileMaker, this file gets replaced by a FileMaker export, the same way courses work today.
