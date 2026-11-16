# Drupal setup for the catalog (after the Drupal 10/11 upgrade)

The builder makes everything. Drupal **pulls** it with the Feeds module, so no Drupal password lives on the catalog computer.

```
FileMaker export ──► catalog-builder ──► publish folder (site/)
                                         ├── current/        digital catalog, rebuilt every run
                                         ├── 2026-27/        edition of record (frozen once with --freeze)
                                         ├── catalog-years.js
                                         └── feeds/courses.csv · programs.csv · addenda.csv
                                                    ▲
                     Drupal Feeds (cron) ───────────┘  → Course, Program, Addendum nodes → Views
```

## 1. Where the publish folder lives

Pick one and put its public address in the builder's `config.json` as `"site_url"` (used in feed links):

| Option | Address | Notes |
|---|---|---|
| GitHub Pages (IECC org) | `https://catalog.iecc.edu` | Free, full version history, one DNS CNAME. Publish = commit the folder in GitHub Desktop. |
| Drupal public files | `https://iecc.edu/sites/default/files/catalog/` | Builder writes to a mapped share of `sites/default/files/catalog`. No history. |
| IIS web server | `https://<server>/catalog/` | Fully internal; IT maps the share. |

The site is plain HTML/CSS/JS with relative links, so it works the same in any of them (and from a file share for proofing).

## 2. Modules

- **Feeds** (pick the release that matches your Drupal version on drupal.org/project/feeds)
- **Feeds Tamper** (optional: split campus lists, trim text)
- Core: Views, Link, Options. CSV only, so the extra JSON parser module isn't needed.

## 3. Content types and fields

Machine names are suggestions; keep them stable because the Feeds mappings point at them.

**Catalog course** (`catalog_course`)

| Field | Type | Feed column |
|---|---|---|
| Title | (node title) | `code` + `title` via Tamper, or `title` |
| `field_course_code` | Text (plain), unique per year | `code` |
| `field_catalog_year` | List (text) or term | `catalog_year` |
| `field_subject` | Taxonomy term (auto-create) | `subject` |
| `field_prefix` | Text (plain) | `prefix` |
| `field_credits` | Decimal | `credits` |
| `field_variable_credit` | Boolean | `variable` (True/False) |
| `field_delivery` | Text (plain) | `delivery` |
| `field_repeatable` | Integer | `repeatable` |
| `field_campuses` | List (text), multiple: FCC, LTC, OCC, WVC | `campuses` (Tamper: explode on space) |
| `field_iai` | Text (plain), multiple | `iai` (Tamper: explode on space) |
| `field_prerequisite` | Text (long) | `prerequisite` |
| `field_corequisite` | Text (long) | `corequisite` |
| Body | Text (long) | `description` |
| `field_catalog_link` | Link | `url` |

**Catalog program** (`catalog_program`): `guid`, `catalog_year`, `code`, `title`, `award`, `type` (Degree / Certificate / Transfer), `meta_major` (term), `department` (term), `campuses` (multiple), `url` (my.iecc.edu page), `page` (link to the program in the digital catalog).

**Catalog addendum** (`catalog_addendum`): `guid`, `catalog_year`, `number`, `effective` (date), `title`, `summary` (body), `pdf` (link).

## 4. Feed types (one per content type)

- Fetcher: **Download from URL**: `<site_url>/feeds/courses.csv` (programs.csv, addenda.csv)
- Parser: **CSV**, delimiter `,`, header row on
- Processor: Node of the matching type. **Update existing nodes**. Unique target: **Feed GUID ← `guid`** (e.g. `2026-27:ACC 2101`)
- **Create new revisions**: on (every change is on record)
- **Items no longer in the feed**: *Unpublish* (never delete)
- Import period: **every 6 hours** (cron must be running)

`guid` contains the catalog year, so when the 2027–28 edition is frozen its courses arrive as new nodes and the 2026–27 nodes stay untouched. To freeze a year in Drupal, turn that year's feed off (or leave it; rows for an old year stop appearing in the feed).

## 5. Views

- **Course search**: exposed filters for catalog year, subject, campus, keyword. Link each title to `field_catalog_link` (the digital catalog) or a node page.
- **Programs**: grouped by meta major, filter by campus and type.
- **/catalog landing**: current edition button, year archive list, latest addenda.
- **Program pages elsewhere on iecc.edu**: replace hand-typed requirements with a View block or a link to the program in the digital catalog.

## 6. Matching the digital catalog's look

Add the builder's `catalog_builder/assets/site.css` (and `fonts/`) to the theme as a library and attach it to the catalog views. It uses the same class names as the digital catalog (`.course`, `.program`, `.camp i.on.FCC`, `.tbl`), so a View row template that outputs the same markup looks identical. Or link straight to the digital catalog pages for full program detail.

## 7. Running it

```
catalog-builder.exe --site "\\server\Catalog\site" --site-url https://catalog.iecc.edu
catalog-builder.exe --site "\\server\Catalog\site" --freeze      # once a year, when the catalog is approved
```

- Every run refreshes `current/` and `feeds/`, checks trustees and policies, and lists course changes since the edition of record in the report.
- **Addenda**: add a row to `content/addenda/2026-27.csv` (number, effective, title, summary, pdf, approved=yes). The next run adds it to the 2026-27 edition's addenda page, the current catalog's banner, and `feeds/addenda.csv`. The frozen pages themselves are never rebuilt.
