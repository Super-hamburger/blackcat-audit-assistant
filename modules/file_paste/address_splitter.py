import re

MAIN_ADDRESS_LIMIT = 16

BUILDING_KEYWORDS = [
    "マンション", "アパート", "ハイツ", "コーポ", "メゾン", "レジデンス",
    "パレス", "ビル", "ハウス", "シャーメゾン", "グラン", "コート",
    "ヴィラ", "荘", "寮", "団地", "棟", "号室", "ルーム"
]


def normalize_text(value):
    if value is None:
        return ""
    return str(value).strip()


def compact_spaces(value):
    value = normalize_text(value)
    value = re.sub(r"[\u3000\s]+", " ", value)
    return value.strip()


def has_digit(value):
    return bool(re.search(r"[0-9０-９]", value or ""))


def find_building_split(street):
    street = compact_spaces(street)
    if not street:
        return "", ""

    if " " in street:
        left, right = street.split(" ", 1)
        return left.strip(), right.strip()

    for keyword in BUILDING_KEYWORDS:
        pos = street.find(keyword)
        if pos > 0:
            return street[:pos].strip(), street[pos:].strip()

    # 10-8下日佐ビル5 -> 10-8 / 下日佐ビル5
    match = re.match(r"^(.+?[0-9０-９]+(?:[-－ー丁目番地号][0-9０-９]*)*)([ァ-ヶ一-龥A-Za-z].*[0-9０-９号室]?)$", street)
    if match:
        main_part = match.group(1).strip()
        building_part = match.group(2).strip()
        if len(main_part) >= 3 and len(building_part) >= 2:
            return main_part, building_part

    return street, ""


def split_town_and_block(full_address):
    """
    Human-friendly split:
    広島県広島市佐伯区吉見園4-25-2
    -> 広島県広島市佐伯区吉見園 / 4-25-2

    It finds the first digit that begins the chome/block number after a
    Japanese town name. This is more natural than splitting by fixed length.
    """
    text = compact_spaces(full_address)
    if not text:
        return "", ""

    # Do not split immediately after 丁目, because "4丁目10-8" should keep
    # "4丁目" with the town side if possible.
    digit_pattern = r"[0-9０-９]"
    for match in re.finditer(digit_pattern, text):
        idx = match.start()
        left = text[:idx]
        right = text[idx:]

        if len(left) < 8:
            continue

        # Only split when the left side ends as a Japanese place name.
        if not re.search(r"[一-龥ぁ-んァ-ヶ]$", left):
            continue

        # Right side should look like a block number.
        if not re.match(r"^[0-9０-９]+(?:[-－ー][0-9０-９]+){0,4}", right):
            continue

        return left.strip(), right.strip()

    return text, ""


def preferred_split_index(text, limit):
    if len(text) <= limit:
        return len(text)

    candidates = []
    for i, ch in enumerate(text[:limit], start=1):
        if ch in "都道府県市区郡町村丁目番地号-－ー":
            candidates.append(i)

    valid = [idx for idx in candidates if idx >= 8]
    if valid:
        return valid[-1]

    return limit


def split_delivery_address(prefecture, city, street, apartment):
    prefecture = normalize_text(prefecture)
    city = normalize_text(city)
    street = compact_spaces(street)
    apartment = compact_spaces(apartment)

    street_main, street_building = find_building_split(street)

    main_address = f"{prefecture}{city}{street_main}"
    building_parts = []
    if street_building:
        building_parts.append(street_building)
    if apartment:
        building_parts.append(apartment)

    building_address = " ".join(part for part in building_parts if part).strip()

    if len(main_address) <= MAIN_ADDRESS_LIMIT:
        return main_address, building_address

    # New v2.1 rule: if the address is too long and contains a clear town name
    # followed by block numbers, move the block numbers to M column.
    town_left, block_right = split_town_and_block(main_address)
    if block_right and len(town_left) >= 8:
        combined_building = " ".join(part for part in [block_right, building_address] if part).strip()
        return town_left, combined_building

    split_at = preferred_split_index(main_address, MAIN_ADDRESS_LIMIT)
    left = main_address[:split_at].strip()
    overflow = main_address[split_at:].strip()

    combined_building = " ".join(part for part in [overflow, building_address] if part).strip()
    return left, combined_building
