# Nightly catalog build: server setup (for IT)

Everything runs on the **FileMaker Server machine**. Nobody has to export by hand or leave a PC on.

```
02:00  FileMaker Server schedule "Catalog Export"
         └─ writes  ...\FileMaker Server\Data\Documents\catalog\courses.xml
02:15  Windows Task Scheduler "IECC Catalog Build"  (run-nightly.bat → catalog-builder.exe --only-if-changed)
         ├─ \\server\Catalog\output\      Marketing: InDesign text files, PDF proof, report.html
         └─ \\vm-webserver\www\catalog\   website (my.iecc.edu/catalog) + Drupal feed CSVs
```

If nothing changed in FileMaker, the content folder or the trustee list, the 02:15 run ends in a second and writes nothing.

---

## 1. FileMaker: the export script

FileMaker Server schedules can only write inside the server's **Documents** folder (or a temporary folder), never straight to a network share. That's why the export lands there and the Windows task picks it up.

In the course file, create a script named **Catalog Export**. In the script editor, set *Compatibility* to **Server** so any step the server can't run is greyed out.

```
Set Error Capture [ On ]
Go to Layout [ "Catalog Export" ]                      // any layout on the course table
Perform Find [ Restore ]                                 // the courses that belong in the catalog
                                                         //   (or Show All Records)
Sort Records [ Restore ; With dialog: Off ]              // prefix, then number
Set Variable [ $path ; Value: Get ( DocumentsPath ) & "catalog/courses.xml" ]
Export Records [ With dialog: Off ; "$path" ; XML (FMPXMLRESULT) ; Create folders: On ]
If [ Get ( LastError ) ≠ 0 ]
    Exit Script [ Text Result: "Export failed: " & Get ( LastError ) ]
End If
```

**Fields to export** (the builder reads them by name, so order doesn't matter):
`CRSM_SUBNUM`, `CRSM_TITLE_COURSE`, `CRSM_DESCRIPTION`, `CRSM_DESCRIPTION_APPEND`, `CRSM_CREDIT_HOURS`, `CRSM_CREDIT_VARIABLE`, `CRSM_CREDIT_LECTURE`, `CRSM_CREDIT_LAB`, `CRSM_COLLEGE_FCC`, `CRSM_COLLEGE_LTC`, `CRSM_COLLEGE_OCC`, `CRSM_COLLEGE_WVC`, `CRSM_IAI_1_EXPORT` … `CRSM_IAI_6_EXPORT`. These are the same fields as the manual export used to build this tool.

If *Create folders* isn't offered in your version, make the `catalog` folder inside `Data\Documents` once by hand.

**Schedule it** in the FileMaker Server Admin Console: *Configuration → Schedules → Create Schedule → FileMaker Script*
- Database: the course file · Account: one whose privilege set allows exporting
- Script: **Catalog Export** · Repeat: **Daily, 2:00 AM** · Time limit: 15 minutes
- Run it once by hand, then confirm `courses.xml` exists in `Data\Documents\catalog\`.

---

## 2. Windows: the builder

1. Unzip the download from GitHub into **`C:\CatalogBuilder\`** on the FileMaker server.
2. Copy the **`content`** folder from the zip to **`\\server\Catalog\content`**. That's where the catalog owner edits section text, addenda and program files. The exe only reads it.
3. Copy `deploy\config.server.json` to `C:\CatalogBuilder\config.json` and check the paths:

| Key | What it is |
|---|---|
| `export` | the file the FileMaker schedule writes |
| `content` | the shared content folder (section text, addenda, programs) |
| `out` | Marketing's review folder |
| `site` | the website folder on vm-webserver |
| `site_url` | the public address of that folder |
| `preview` | `true` keeps search engines out while drafting; set `false` at launch |

4. **Service account.** Create or choose a Windows account that has:
   - read on `...\FileMaker Server\Data\Documents\catalog\`
   - read on `\\server\Catalog\content`, write on `\\server\Catalog\output` and `\\vm-webserver\www\catalog` (that folder only)
   - the *Log on as a batch job* right on the FileMaker server
5. In an **elevated PowerShell**:
   ```
   cd C:\CatalogBuilder
   powershell -ExecutionPolicy Bypass -File .\deploy\install-scheduled-task.ps1
   ```
   Enter the service account when asked. It schedules **IECC Catalog Build** daily at 2:15 AM.
6. **Test:** `Start-ScheduledTask -TaskName "IECC Catalog Build"`, then check `C:\CatalogBuilder\logs\`, `\\server\Catalog\output\report.html` and https://my.iecc.edu/catalog.

**Windows SmartScreen / antivirus:** the exe isn't code-signed. If it's blocked, allow `C:\CatalogBuilder\catalog-builder.exe` by path or hash.

---

## 3. Once a year

When the new catalog is approved, freeze its edition of record (it's never overwritten afterward):
```
C:\CatalogBuilder\catalog-builder.exe --freeze
```

## 4. Updating the builder

Download the new zip from GitHub (Actions → latest run → Artifacts, or the Releases page) and replace **only** `catalog-builder.exe`. `config.json`, `logs\` and the shared `content` folder stay as they are.

## Troubleshooting

| Symptom | Check |
|---|---|
| Report says the export is unchanged for days | FileMaker Admin Console → Schedules → last run / errors; does `courses.xml` have today's date? |
| `Access is denied` in the log | service-account rights on the output or www share |
| Website not updating | `site` path in config.json; write rights on `www\catalog`; `preview` doesn't block updates |
| "Trustee check failed" warning | the server can't reach iecc.edu over HTTPS; the build still finishes |
