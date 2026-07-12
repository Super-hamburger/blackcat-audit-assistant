# File Paste Rack and Address Design

## Scope

Extend only the one-piece delivery conversion path. The new Black Cat source format and UI remain unchanged.

## One-Piece Output

- Read shelf location from `货架`, with `货位` as a compatible alias.
- Write the shelf location to `AB`.
- Write `SKU` followed directly by `*1` to `AD`.
- Sort rows by shelf location before output. Numeric-leading values sort first by hyphen-separated numeric segments; letter-leading values sort after numeric values; blank or unparseable values remain stable at the end.

## Address Allocation

Combine `州`, `城市`, `地址`, and `地址2`. Measure full-width characters as 1 and half-width characters as 0.5.

- `L`: maximum width 12.
- `M`, `N`, and `O`: maximum width 16 each.
- Prefer semantic boundaries such as spaces, address/block boundaries, and building-name boundaries. Fall back to width-safe splitting.
- When content remains after `O`, preserve it in `O` and mark that cell red.
- Write the recipient company to `O` only when `O` is not required for address content.

## Formatting

Keep existing yellow address-split, red missing-required, and green item-split marking. Remove the generated color-legend row.

## Verification

Add focused converter tests for mapping, sorting, width allocation, overflow marking, company placement, legacy one-piece input, and unchanged new Black Cat behavior. Update the required changelog files.
