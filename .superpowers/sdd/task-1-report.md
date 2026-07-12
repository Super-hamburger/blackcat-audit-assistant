# Task 1 Report: Converter behavior and tests

## Scope

Implemented only the Task 1 files from the brief:

- `modules/file_paste/address_splitter.py`
- `modules/file_paste/converter.py`
- `tests/test_file_paste_converter.py`

No UI, changelog, release, or version files were changed.

## TDD Record

### RED

Command:

```powershell
& 'C:\Users\Admin\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m unittest tests.test_file_paste_converter -v
```

Output:

```text
test_new_blackcat_keeps_existing_ab_ad_mapping_and_item_split_marking (tests.test_file_paste_converter.UploadConverterTest.test_new_blackcat_keeps_existing_ab_ad_mapping_and_item_split_marking) ... ok
test_one_piece_allocates_address_columns_marks_overflow_and_uses_company_in_o (tests.test_file_paste_converter.UploadConverterTest.test_one_piece_allocates_address_columns_marks_overflow_and_uses_company_in_o) ... FAIL
test_one_piece_uses_shelf_alias_sorts_rows_and_maps_sku_to_ad (tests.test_file_paste_converter.UploadConverterTest.test_one_piece_uses_shelf_alias_sorts_rows_and_maps_sku_to_ad) ... FAIL

======================================================================
FAIL: test_one_piece_allocates_address_columns_marks_overflow_and_uses_company_in_o (tests.test_file_paste_converter.UploadConverterTest.test_one_piece_allocates_address_columns_marks_overflow_and_uses_company_in_o)
----------------------------------------------------------------------
Traceback (most recent call last):
  File "C:\Users\Admin\Desktop\BlackCatAuditAssistant\BlackCatAuditAssistant_Temp_Workspace_FilePaste_4_4_1\tests\test_file_paste_converter.py", line 177, in test_one_piece_allocates_address_columns_marks_overflow_and_uses_company_in_o
    self.assertEqual(sheet["M2"].value, "BuildingAlpha BuildingBeta")
AssertionError: 'Buil[17 chars]gBeta BuildingGamma BuildingDelta BuildingEpsi[20 chars]m505' != 'Buil[17 chars]gBeta'
- BuildingAlpha BuildingBeta BuildingGamma BuildingDelta BuildingEpsilon BuildingZeta Room505
+ BuildingAlpha BuildingBeta


======================================================================
FAIL: test_one_piece_uses_shelf_alias_sorts_rows_and_maps_sku_to_ad (tests.test_file_paste_converter.UploadConverterTest.test_one_piece_uses_shelf_alias_sorts_rows_and_maps_sku_to_ad)
----------------------------------------------------------------------
Traceback (most recent call last):
  File "C:\Users\Admin\Desktop\BlackCatAuditAssistant\BlackCatAuditAssistant_Temp_Workspace_FilePaste_4_4_1\tests\test_file_paste_converter.py", line 125, in test_one_piece_uses_shelf_alias_sorts_rows_and_maps_sku_to_ad
    self.assertEqual(
AssertionError: Lists differ: ['REF-LETTER', 'REF-10', 'REF-2', 'REF-WEIRD', 'REF-BLANK'] != ['REF-2', 'REF-10', 'REF-LETTER', 'REF-WEIRD', 'REF-BLANK']

First differing element 0:
'REF-LETTER'
'REF-2'

- ['REF-LETTER', 'REF-10', 'REF-2', 'REF-WEIRD', 'REF-BLANK']
+ ['REF-2', 'REF-10', 'REF-LETTER', 'REF-WEIRD', 'REF-BLANK']

----------------------------------------------------------------------
Ran 3 tests in 0.373s

FAILED (failures=2)
```

### GREEN

Command:

```powershell
& 'C:\Users\Admin\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m unittest tests.test_file_paste_converter -v
```

Output:

```text
test_new_blackcat_keeps_existing_ab_ad_mapping_and_item_split_marking (tests.test_file_paste_converter.UploadConverterTest.test_new_blackcat_keeps_existing_ab_ad_mapping_and_item_split_marking) ... ok
test_one_piece_allocates_address_columns_marks_overflow_and_uses_company_in_o (tests.test_file_paste_converter.UploadConverterTest.test_one_piece_allocates_address_columns_marks_overflow_and_uses_company_in_o) ... ok
test_one_piece_uses_shelf_alias_sorts_rows_and_maps_sku_to_ad (tests.test_file_paste_converter.UploadConverterTest.test_one_piece_uses_shelf_alias_sorts_rows_and_maps_sku_to_ad) ... ok

----------------------------------------------------------------------
Ran 3 tests in 0.232s

OK
```

## Files Changed

- `modules/file_paste/address_splitter.py`
- `modules/file_paste/converter.py`
- `tests/test_file_paste_converter.py`

## Change Summary

- Added focused `unittest` coverage for one-piece shelf aliasing, shelf sort order, AB/AD mapping, address allocation across `L/M/N/O`, overflow red marking, company placement, no legend row, and preserved new-Black-Cat AB/AD behavior plus item split marking.
- Added width-aware address splitting that measures full-width characters as `1` and half-width characters as `0.5`, prefers semantic boundaries before width-only cuts, and exposes `L/M/N/O` plus overflow state.
- Updated one-piece conversion to read `货架` first with `货位` fallback, sort by the approved shelf rules, write shelf to `AB`, write `SKU + "*1"` to `AD`, use `O` for company only when address content does not need it, and stop writing the legend row.

## Self-Review

- Confirmed the RED run failed for the intended reasons before production changes.
- Confirmed the GREEN run passes on the focused converter test file after the production changes.
- Kept the change scoped to the three Task 1 implementation files plus this report.
- Verified the new Black Cat case still maps `AB` from `sku` and `AD/AF` from `明细`, including existing green split marking.

## Concerns

- Only the focused Task 1 test file was run. No broader regression suite was executed in this task.

## Commit

- Commit SHA: 0b9ed28
