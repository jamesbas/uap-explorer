# WAR.gov UFO Release 01 Download Package

This package contains the CSV manifest and two download scripts that will download every unique file link from the `PDF | Image Link` column and create a single ZIP.

The CSV contains 145 link rows, with 130 unique downloadable file URLs. The scripts deduplicate links so duplicate URLs are only downloaded once.

## Windows PowerShell

1. Put `uap-csv.csv` and `download_and_zip_ufo_files.ps1` in the same folder.
2. Open PowerShell in that folder.
3. Run:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\download_and_zip_ufo_files.ps1
```

Output:

- `ufo_release_01_files\` — downloaded PDFs/images
- `ufo_release_01_download_manifest.csv` — status and errors
- `war_gov_ufo_release_01_documents.zip` — the final single ZIP

## Python

```bash
python download_and_zip_ufo_files.py --csv uap-csv.csv
```

The scripts skip files that already exist, so you can safely rerun them if a download fails.
