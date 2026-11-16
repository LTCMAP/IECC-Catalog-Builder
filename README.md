# IECC catalog-builder

Turns the FileMaker course export into every version of the catalog's course section:

| Output | Path | Used for |
|---|---|---|
| InDesign Tagged Text | `out/indesign/<PREFIX>.txt` (one per subject) + `_ALL-COURSES.txt` | Placed **and linked** in the InDesign catalog. When data changes, the Links panel flags the story and you click Update. |
| Print proof | `out/print/course-descriptions.pdf` (+ a short `-sample.pdf`) | The designed course section, tagged PDF. Good for proofing or as a stand-in if InDesign isn't used. |
| Web catalog | `out/web/course-descriptions.html` | Single-file, searchable, accessible course list (search, subject, college, IAI filters). |
| Data | `out/data/courses.json`, `courses.csv` | Clean data for Drupal Feeds or anything else. |
| Report | `out/report.html` | Data checks, plus **what changed since the last build** (your addendum draft). |

Nothing is published automatically. The builder makes drafts; a person reviews the report and updates the InDesign links.

---

## 1. FileMaker export (one-time setup)

1. In FileMaker, find the courses to publish (the catalog's found set).
2. **File › Export Records…** › type **XML** › grammar **FMPXMLRESULT**, no XSL.
3. Field export order (names matter, order doesn't):
   `CRSM_SUBNUM, CRSM_DESCRIPTION, CRSM_IAI_1_EXPORT … CRSM_IAI_6_EXPORT, CRSM_COLLEGE_FCC/LTC/OCC/WVC, CRSM_TITLE_COURSE, CRSM_CREDIT_VARIABLE, CRSM_CREDIT_HOURS, CRSM_CREDIT_LAB, CRSM_CREDIT_LECTURE, CRSM_DESCRIPTION_APPEND`
4. Save the export to the shared folder, e.g. `\\server\Catalog\exports\courses.xml`.
5. Save it all as a script step (**Export Records**, "Perform without dialog") on a button called **Export for Catalog**.

## 2. Run the builder

```
python build.py --export "\\server\Catalog\exports\courses.xml" --out "\\server\Catalog\output"
```

Or put the paths in `config.json` (copy `config.example.json`) and just run `python build.py`.

Options:
- `--only-if-changed`: does nothing if the export is identical to last time. Use this for scheduled runs.
- `--no-pdf`: skips the PDF proof (about 1 minute faster).
- `--sample ACC,LSC,WEL`: sets which subjects go into the short sample PDF.

Requirements: Python 3.10+, then `pip install -r requirements.txt`.

### Making it a double-click .exe (no Python on her machine)

```
pip install pyinstaller
pyinstaller --onefile --name catalog-builder --add-data "catalog_builder/assets;catalog_builder/assets" --add-data "config;config" build.py
```

Put `dist/catalog-builder.exe` and a `config.json` in `\\server\Catalog\builder\`. To update the builder for everyone, replace that one file.

### Scheduled runs (Windows Task Scheduler)

Action: `\\server\Catalog\builder\catalog-builder.exe --only-if-changed` · Trigger: daily, or at log on.
(`run-catalog-build.bat` does the same thing for a manual double-click.)

## 3. InDesign setup (one-time)

1. **Preferences › File Handling** › check **Create Links When Placing Text and Spreadsheet Files**.
2. Fonts: **Poppins** and **Lato** (both free; both on Adobe Fonts).
3. In the catalog document, thread the course frames, then **File › Place** each `out/indesign/<PREFIX>.txt`, or `_ALL-COURSES.txt` for a single long story.
4. The tagged files define these styles. Restyle them in InDesign however you like; on later updates choose **Use document style definitions** so your design wins:
   - Paragraph styles: Subject Head · Course Head · Course Meta · Course Description · Course Requisite
   - Character styles: Course Code · Credits · Campus On · Campus Off · IAI · Requisite Label
   - Course Head uses a **right-indent tab** to push credits to the column edge.
5. After a rebuild, the **Links** panel shows modified stories ⚠ › select › **Update Link**.

> ⚠ Updating a link replaces that story. Make content edits in **FileMaker**, not in InDesign, or they'll be overwritten (and they should live in FileMaker anyway).

## 4. Drupal (optional)

Point a Feeds importer at `out/data/courses.json` (or `.csv`) mapped to a "Course" content type, keyed on `code`. Or embed `course-descriptions.html` as-is.

## Checks performed

Errors: missing descriptions, draft/placeholder text, duplicate codes, invalid codes.
Warnings: non-standard PREREQUISITE labels, broken apostrophes (`Labor?s`), references to courses not in the export, lecture + lab ≠ credit hours, invalid variable-credit flags, prefixes missing from the prefix list, and differences from the printed 2026–27 catalog (`config/print_comparison_2026-27.json`; set `"compare_to_print": false` in config.json to turn this off).
Notes (auto-cleaned in output): stray spaces, odd characters in campus fields, identical descriptions, cross-listed titles.

## Files

```
build.py                     entry point
config/prefixes.json         prefix → subject name (from the catalog's Course Prefixes page)
config/print_comparison_…    one-time comparison against the printed 2026–27 PDF
catalog_builder/model.py     reads the FileMaker XML, normalizes fields, splits out prerequisites
catalog_builder/checks.py    data-quality rules
catalog_builder/outputs.py   print PDF, InDesign tagged text, data, change detection
catalog_builder/web.py       searchable web page
catalog_builder/report.py    build report
catalog_builder/assets/      print.css + fonts (Poppins, Lato — SIL Open Font License)
```
