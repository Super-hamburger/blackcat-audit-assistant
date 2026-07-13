# File Paste Rebuild Design

## Goal

Rebuild the file-paste conversion path from the supplied workbooks, without
carrying forward the previous file-paste mapping rules. Both supported source
formats must produce a Black Cat upload workbook whose first-row header,
column order, and column count exactly match
`0713-黑猫宅急便模版（泉南仓库）(100) (改1).xlsx`.

The existing 4.4.0 to 4.4.1 changes outside this feature remain intact.

## Inputs and Detection

The converter supports exactly two source layouts, recognized from their
headers rather than their filenames:

| Source layout | Identity field | Source-specific fields |
| --- | --- | --- |
| `0713-黑猫新版(100).xlsx` | `单号` | recipient address, detailed address, `sku`, `明细` |
| `202607137740一件代发.xlsx` | `参考单号` | `SKU`, `数量`, `货架`, address parts |

Rows without an identity value are ignored. Any other layout is rejected with
a clear message that lists the required identifying headers.

## Output Template

The application will ship a canonical Black Cat template derived from the
usable `(改1)` workbook. Conversion starts by copying that template, clearing
only data rows, and then populating the known output fields. This avoids
reconstructing a partial header list in code and preserves all 98 columns in
their required positions.

The output keeps the target's fixed sender/default values. The output date is
the conversion date in `yyyyMMdd` form. Text identifiers such as order IDs,
telephone numbers, postcodes, SKUs, and shelves are always written as text.

## Common Recipient Address Allocation

Both source formats use the same address allocator:

1. Build one recipient address string. The Black Cat source uses `收件地址`
   followed by `详细地址`; the one-piece source uses `州`, `城市`, `地址`, and
   `地址2`.
2. Split that string left to right into L, M, N, and O, respecting these
   third-party limits: L no more than 12 full-width characters; M no more than
   16; N and O no more than 25 each.
3. Measure a full-width character as one unit and a half-width character as
   half a unit. Prefer natural boundaries (spaces and address separators),
   but never exceed a column limit in order to keep a longer word together.
4. If the whole address cannot fit in L:O, fail that conversion with the order
   ID and the address length instead of silently truncating an address.

Company data is not written into L:O because those four columns are reserved
for the recipient address under the usable target layout.

## Product, Quantity, and Shelf Rules

For the Black Cat source:

- AB receives `sku` unchanged.
- AD receives `明细` unchanged, including values such as `*1+*1`.

For the one-piece source:

- AB receives `货架` unchanged.
- AD contains a comma-separated SKU/quantity list. Pair the first SKU with
  the first `*quantity`, the second SKU with the second `*quantity`, and so
  on: `sku-a,sku-b` plus `*1+*1` becomes `sku-a*1,sku-b*1`.
- A single SKU with numeric `数量` becomes `sku*数量`.
- Multiple SKUs with a numeric total equal to the number of SKUs becomes one
  `*1` entry per SKU.
- A multiple-SKU row with only a numeric total that does not identify each
  SKU's individual quantity is rejected. The source does not contain enough
  information to safely choose between distributions such as `*3+*2`.

These rules keep quantities explicit and prevent a plausible but incorrect
upload when the source has insufficient detail.

## One-Piece Shelf Ordering

Only one-piece rows are reordered:

1. A row with exactly one shelf location is sortable. Split it on hyphens and
   compare segments left to right in ascending order.
2. Numeric segments compare numerically, so `2-1-1-1` precedes `10-1-1-1`.
   Numeric-leading shelves come before letter-leading shelves.
3. If earlier segments match, compare the next segment, so
   `13-3-3-2` precedes `13-6-3-2`.
4. A shelf cell containing more than one location (for example, a comma
   separated value) is not compared. Those rows retain their source order and
   are placed after every single-shelf row.

Black Cat source rows retain their source order.

## Implementation Boundaries

- Replace the current converter's legacy mappings rather than layering new
  conditions over them.
- Separate source readers, address allocation, item/quantity pairing, shelf
  sorting, and template writing into small testable functions.
- Keep the existing module entry point and UI workflow unchanged.
- Retain the currently delivered 4.4.1 changes outside `file_paste`.

## Error Handling

The converter must stop before writing an output file when it encounters an
unsupported source, an overlong recipient address, a missing required identity
field on an otherwise populated row, or an ambiguous multi-SKU quantity. Its
message must identify the affected order and the field that needs correction.

## Verification

Focused tests will use small synthetic workbooks plus the supplied examples
to verify:

- exact 98-column target header and order;
- both source-format mappings;
- common L/M/N/O address limits;
- SKU-to-quantity pairing, including `*1+*1`, `*3`, and `*2`;
- rejection of unresolvable multi-SKU totals;
- shelf placement in AB and all shelf-ordering rules;
- multiple-shelf rows at the bottom;
- preservation of the non-file-paste 4.4.1 behavior.

The final build will be packaged and opened for manual testing.
