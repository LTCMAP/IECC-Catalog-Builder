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

## Board policies (`policies/`)

`policies/policy-register.csv` lists every Board policy (number, title, section, status, adopted, last revised) and points to `policies/<number>.md`, the policy's text.

- Put `{{policy 500.4}}` on its own line in any section file to print that policy's current text, followed by a source line with its adopted and revised dates.
- Write `{{policy-ref 500.4}}` inside a sentence to get "Course Repeat Policy (Board Policy 500.4)".
- Set `"policies_reviewed"` in `catalog.json` to the date the catalog's policy text was last checked. The build report lists every policy revised after that date.
- The report also flags references to deleted policies, numbers missing from the register, and dates where the manual's contents page and the policy text disagree.

To refresh from the website, download the Policy Manual PDFs (iecc.edu/policymanual) into one folder, rename them `POLICY_CONTENTS.pdf` and `POLICY_<100–800>_<CODE>.pdf`, then run:
`pip install pdfplumber` then `python tools/import_policies.py <that folder>`

## Board of Trustees (`board.json`)

The Board section prints from `board.json` (wherever `{{trustees}}` appears in `sections/board.md`). Every build first checks the live trustees page (`trustees_url` in `catalog.json`) and reports any difference as an error: a trustee added or removed, a changed role or hometown, or new Board Treasurer/Secretary. If the site can't be reached, the report says so as a warning.

When the website is right, run the builder once with `--update-trustees` to copy it into `board.json`. A trustee change also counts as "changed", so `--only-if-changed` runs rebuild when the board changes even if the FileMaker export didn't.
