# Address L Column Optimization Design

## Scope

Adjust only the file-paste Japanese address allocator. Source recognition,
template headers, address overflow handling, and shelf sorting remain
unchanged.

## Address Allocation

- `L` accepts at most 13 full-width characters.
- `M`, `N`, and `O` keep their existing limits of 16, 25, and 25 full-width
  characters.
- `L` begins with the prefecture and municipality information when present:
  prefecture, city, ward, county, town, or village.
- After those administrative components, the allocator consumes the following
  address text up to the remaining L capacity. It may split the next token at
  the width-safe boundary so that unused L capacity is filled before content
  moves to M.
- Content that does not fit in L continues through M, N, and O with the
  existing semantic token allocation and overflow marking behavior.

## Compatibility

- Width accounting remains full-width = 1 and ASCII/half-width = 0.5.
- No address characters may be lost or reordered.
- Existing M/N/O limits and O-overflow red marking remain unchanged.

## Verification

- Add a focused regression test that proves L contains the prefecture and
  municipality prefix and is filled to width 13 when additional address text
  exists.
- Keep coverage proving M/N/O width limits and O overflow behavior.
