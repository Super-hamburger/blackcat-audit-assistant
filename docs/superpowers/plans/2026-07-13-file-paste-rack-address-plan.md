# File Paste Rack and Address Implementation Plan

## Task 1: Converter behavior and tests

1. Add focused `unittest` coverage for the real `UploadConverter` output: `货架` and `货位` aliases, missing shelf compatibility, numeric-before-letter shelf ordering, `AB = shelf`, `AD = SKU + "*1"`, address width allocation, O overflow red marking, company placement, no legend row, and unchanged new-Black-Cat mapping.
2. Run the focused test file and confirm it fails before production changes.
3. Extend only `modules/file_paste/address_splitter.py` and `modules/file_paste/converter.py` with the approved rules:
   - Apply new shelf sorting and AB/AD mapping only to the one-piece source type; the new Black Cat source type must retain its existing behavior.
   - Read `货架` first and `货位` as an alias. Missing shelf data must not prevent conversion; blank values sort after valid numeric and letter values.
   - Numeric-leading shelf identifiers sort first by hyphen-separated numeric parts left-to-right. Letter-leading identifiers sort after numeric identifiers and lexically among themselves. Preserve stable order for empty or unparseable values.
   - Combine `州`, `城市`, `地址`, and `地址2`, measuring full-width characters as 1 and half-width characters as 0.5. Split into L (12), then M/N/O (16 each), preferring address, block-number, space, and building-name boundaries before width-only splitting.
   - When address content remains after O, preserve it in O and apply the existing missing-required red fill to O. Write `收件公司` to O only when O is unused by address content.
   - Preserve existing yellow address, red required-field, and green item-split cell marking. Do not write the generated color-legend row.
4. Re-run the focused tests and commit the completed task.

## Task 2: Change records and integration checks

1. Update `data/changelog.json` and `docs/CHANGELOG_FULL.md` for the file-paste behavior change.
2. Run focused tests, static compilation, and JSON validation.
3. Commit the completed task.
