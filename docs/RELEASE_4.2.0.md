# BlackCat Audit Assistant 4.2.0 Release

Release date: 2026-07-04

## Highlights

- Public release version converted from `4.1.7-test` to `4.2.0`.
- Label recognition now uses candidate scoring and confidence checks.
- Low-confidence pages stop the task and are exported for manual review.
- `recognition_report.csv` records page-level recognition results and reasons.
- Release package keeps remote update discovery through `update_manifest.json`.

## Verification

- `compileall app.py ui core modules`
- JSON validation for `version.json`, `data/changelog.json`, and `updater/update_manifest.example.json`
- Source `--self-test`
- Packaged EXE `--self-test`

## Update Hosting

- GitHub Release hosts `BlackCatAuditAssistant_Setup_4.2.0.zip`.
- GitHub Pages hosts `update_manifest.json`.
