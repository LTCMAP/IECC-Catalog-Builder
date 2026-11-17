# Local test: static catalog on one Windows PC

This runs the whole pipeline in a single folder on one computer. Nothing is published and no server is touched. When the FileMaker export location and Marketing's share are confirmed, you change three paths in `config.json` and you're on the real setup (see `SERVER-SETUP.md`).

## 1. Make the test folder

Create **`C:\CatalogTest\`** with four empty folders. The builder creates `output`, `marketing` and `site` itself, but `exports` must exist.

```
C:\CatalogTest\
├── builder\      ← the download goes here
├── exports\      ← the FileMaker XML goes here (courses.xml)
├── output\       (created by the builder: InDesign files, PDFs, report, digital catalog)
├── marketing\    (stand-in for \\mydo\marketing\catalog: IDML + script + PDF + report)
└── site\         (the static catalog website: current\ and 2026-27\)
```

## 2. Download and unzip

1. Download **https://github.com/LTCMAP/IECC-Catalog-Builder/releases/latest/download/catalog-builder-windows.zip**
2. Right-click the zip → **Properties** → tick **Unblock** (if shown) → OK. This stops Windows warning about every file inside.
3. Extract everything into **`C:\CatalogTest\builder\`**. You should see `catalog-builder.exe`, `run-catalog-build.bat`, `config.example.json`, and the folders `weasyprint`, `content`, `deploy`, `docs` and `sample`.

## 3. Settings

Copy **`config.example.json`** to **`config.json`** in the same folder. It's already set up for this layout (paths are relative to the builder folder), so there's nothing to edit for the test:

| Setting | Test value | Later (real setup) |
|---|---|---|
| `export` | `..\exports\courses.xml` | the folder FileMaker writes to (to be provided) |
| `content` | `content` | `\\server\Catalog\content` |
| `out` | `..\output` | `\\server\Catalog\output` |
| `marketing_folder` | `..\marketing` | `\\mydo\marketing\catalog` |
| `site` | `..\site` | `\\vm-webserver\www\catalog` |
| `preview` | `true` | `false` at launch |

## 4. Put a FileMaker export in place

Until FileMaker exports on its own:
- **Real data:** in FileMaker, *File → Export Records…*, type **XML**, grammar **FMPXMLRESULT**, with the fields listed in `SERVER-SETUP.md`, saved as **`C:\CatalogTest\exports\courses.xml`**.
- **Quick check without FileMaker:** copy `builder\sample\sample-export.xml` to `exports\courses.xml` (12 courses).

## 5. First run: freeze the 2026–27 static edition

Open a Command Prompt in `C:\CatalogTest\builder\` (in File Explorer, click the address bar, type `cmd`, press Enter) and run:

```
catalog-builder.exe --freeze
```

It takes about 3 minutes; the full-catalog PDF is the slow part. When it finishes:

- **`marketing\`** has `IECC-Academic-Catalog-2026-27.idml`, `Fit catalog pages.jsx`, `full-catalog.pdf` and `report.html`
- **`site\2026-27\index.html`** is the static catalog (the edition of record). Open it in a browser; it works straight from the folder.
- **`site\current\`** is the dynamic version (rebuilt every run)
- **`output\report.html`** lists data problems and what changed

`--freeze` is only for the first run of a catalog year. After that, run **`run-catalog-build.bat`** (or `catalog-builder.exe` with no options). That refreshes `current\`, the IDML and the PDFs, and leaves `2026-27\` untouched.

## 6. Open the IDML in InDesign

1. **Fonts:** the IDML uses the brand fonts **Futura PT** and **Adobe Garamond Pro**. Activate both in Adobe Fonts first, or InDesign will flag them as missing. To use other fonts, add an `indesign_fonts` block to `config.json` (see the README).
2. Double-click the `.idml`. InDesign opens it as a new untitled document; **Save As** an `.indd`.
3. **Fit the pages (once):** page counts in the IDML are estimates. Install the script:
   *Window → Utilities → Scripts*, right-click **User** → **Reveal in Explorer**, copy `Fit catalog pages.jsx` into that folder, then double-click it in the Scripts panel. It adds pages wherever a section runs long and removes empty ones, then reports what it did.
4. Every paragraph uses a named style (Section Title, Body, Course Head, Course Description …), so Marketing restyles the whole catalog by editing styles, not text.

## 7. Moving to the real paths

When IT confirms the locations, edit `config.json`:
- `export`: wherever the FileMaker export lands (the `.bat` on vm-fmpserver can `robocopy` it there)
- `marketing_folder`: `\\mydo\\marketing\\catalog` (in JSON every `\` is written `\\`)
- `site`: `\\vm-webserver\\www\\catalog` when you're ready to publish

Then schedule it with `deploy\install-scheduled-task.ps1` (see `SERVER-SETUP.md`).

## If something goes wrong

| What you see | What to do |
|---|---|
| "Windows protected your PC" | *More info → Run anyway*, or unblock the zip before extracting (step 2) |
| `No export given` / file not found | check `exports\courses.xml` exists and `config.json` sits next to the exe |
| "PDF skipped" in the window | the `weasyprint` folder must sit next to `catalog-builder.exe`; re-extract the zip |
| IDML text shows red overset `+` | run `Fit catalog pages.jsx` (step 6.3) |
| Missing fonts in InDesign | activate Futura PT and Adobe Garamond Pro, or change `indesign_fonts` |
