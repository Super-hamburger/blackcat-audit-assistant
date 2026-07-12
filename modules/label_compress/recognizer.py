from dataclasses import dataclass, field
import re


HIGH_CONFIDENCE_THRESHOLD = 80


@dataclass
class RecognitionCandidate:
    number: str
    score: int
    method: str
    reason: str
    x0: float = 0.0
    y0: float = 0.0
    x1: float = 0.0
    y1: float = 0.0

    def to_dict(self):
        return {
            "number": self.number,
            "score": self.score,
            "method": self.method,
            "reason": self.reason,
            "x0": self.x0,
            "y0": self.y0,
            "x1": self.x1,
            "y1": self.y1,
        }


@dataclass
class RecognitionResult:
    number: str | None = None
    confidence: int = 0
    method: str = "not-found"
    reason: str = "No tracking-number candidate was found."
    candidates: list[RecognitionCandidate] = field(default_factory=list)

    @property
    def ok(self):
        return bool(self.number) and self.confidence >= HIGH_CONFIDENCE_THRESHOLD

    def to_dict(self):
        return {
            "number": self.number or "",
            "confidence": self.confidence,
            "method": self.method,
            "reason": self.reason,
            "candidates": [candidate.to_dict() for candidate in self.candidates],
        }


class TrackingRecognizer:
    keyword_patterns = [
        "お問い合わせ",
        "お問合せ",
        "送り状",
        "伝票",
        "問合",
        "番号",
        "tracking",
        "inquiry",
    ]
    negative_patterns = [
        "tel",
        "電話",
        "郵便",
        "〒",
        "住所",
        "zip",
        "postal",
        "order",
        "注文",
        "品名",
        "sku",
    ]

    def recognize(self, text, words=None, page_rect=None):
        text = text or ""
        words = words or []
        candidates = []
        candidates.extend(self._from_barcode_text(text, words, page_rect))
        candidates.extend(self._from_separated_numbers(text, words, page_rect))
        candidates.extend(self._from_plain_numbers(text, words, page_rect))
        merged = self._merge_candidates(candidates)

        if not merged:
            return RecognitionResult(candidates=[])

        merged.sort(key=lambda item: item.score, reverse=True)
        best = merged[0]
        if best.score < HIGH_CONFIDENCE_THRESHOLD:
            return RecognitionResult(
                number=None,
                confidence=best.score,
                method="low-confidence",
                reason=f"Best candidate did not reach confidence threshold: {best.reason}",
                candidates=merged[:8],
            )

        return RecognitionResult(
            number=best.number,
            confidence=best.score,
            method=best.method,
            reason=best.reason,
            candidates=merged[:8],
        )

    def extract_from_text(self, text):
        return self.recognize(text).number

    def _from_barcode_text(self, text, words, page_rect):
        candidates = []
        compact = re.sub(r"\s+", "", text)
        for match in re.finditer(r"a(\d{10,20})a", compact, flags=re.IGNORECASE):
            number = match.group(1)
            score = 95 + self._length_bonus(number)
            reason = "barcode wrapped by a...a"
            box = self._locate_number(words, number)
            score += self._position_bonus(box, page_rect)
            candidates.append(self._candidate(number, score, "barcode-text", reason, box))
        return candidates

    def _from_separated_numbers(self, text, words, page_rect):
        candidates = []
        pattern = re.compile(r"(?<!\d)(\d{4})[-\s](\d{4})[-\s](\d{4,8})(?!\d)")
        for match in pattern.finditer(text):
            number = "".join(match.groups())
            box = self._locate_number(words, number) or self._locate_fragment(words, match.group(0))
            score = 76 + self._length_bonus(number)
            reason = "separated tracking-number pattern"
            score += self._context_bonus(text, match.start(), match.end())
            score += self._position_bonus(box, page_rect)
            score -= self._negative_context_penalty(text, match.start(), match.end())
            candidates.append(self._candidate(number, score, "tracking-pattern", reason, box))
        return candidates

    def _from_plain_numbers(self, text, words, page_rect):
        candidates = []
        pattern = re.compile(r"(?<!\d)(\d{10,20})(?!\d)")
        compact_matches = {}
        for match in pattern.finditer(text):
            compact_matches.setdefault(match.group(1), []).append((match.start(), match.end()))

        for number, ranges in compact_matches.items():
            box = self._locate_number(words, number)
            score = 58 + self._length_bonus(number)
            reason = "plain numeric candidate"
            score += min((len(ranges) - 1) * 12, 24)
            score += self._position_bonus(box, page_rect)
            score += max(self._context_bonus(text, start, end) for start, end in ranges)
            score -= max(self._negative_context_penalty(text, start, end) for start, end in ranges)
            candidates.append(self._candidate(number, score, "plain-number", reason, box))

        for word in words:
            raw = str(word.get("text", ""))
            normalized = re.sub(r"\D", "", raw)
            if not re.fullmatch(r"\d{10,20}", normalized or ""):
                continue
            box = (word["x0"], word["y0"], word["x1"], word["y1"])
            score = 56 + self._length_bonus(normalized)
            score += self._position_bonus(box, page_rect)
            candidates.append(self._candidate(normalized, score, "word-number", "word-level numeric candidate", box))

        return candidates

    def _merge_candidates(self, candidates):
        merged = {}
        for candidate in candidates:
            if not self._valid_number(candidate.number):
                continue
            current = merged.get(candidate.number)
            if not current or candidate.score > current.score:
                merged[candidate.number] = candidate
            elif candidate.score + 8 > current.score:
                current.score = min(current.score + 8, 100)
                current.reason += "; repeated candidate"
        return list(merged.values())

    def _valid_number(self, number):
        if not number or not number.isdigit():
            return False
        if len(number) < 10 or len(number) > 20:
            return False
        if len(set(number)) <= 2:
            return False
        return True

    def _length_bonus(self, number):
        if len(number) == 12:
            return 16
        if 10 <= len(number) <= 14:
            return 8
        return 0

    def _context_bonus(self, text, start, end):
        window = text[max(0, start - 80): min(len(text), end + 80)].lower()
        return sum(12 for pattern in self.keyword_patterns if pattern.lower() in window)

    def _negative_context_penalty(self, text, start, end):
        window = text[max(0, start - 80): min(len(text), end + 80)].lower()
        return sum(18 for pattern in self.negative_patterns if pattern.lower() in window)

    def _position_bonus(self, box, page_rect):
        if not box or not page_rect:
            return 0
        page_width = max(float(page_rect.get("width", 1)), 1.0)
        page_height = max(float(page_rect.get("height", 1)), 1.0)
        x0, y0, x1, y1 = box
        cx = ((x0 + x1) / 2) / page_width
        cy = ((y0 + y1) / 2) / page_height
        bonus = 0
        if 0.55 <= cx <= 0.95:
            bonus += 8
        if 0.45 <= cy <= 0.92:
            bonus += 8
        if 0.62 <= cx <= 0.93 and 0.48 <= cy <= 0.90:
            bonus += 10
        return bonus

    def _locate_number(self, words, number):
        if not words:
            return None
        for word in words:
            raw = str(word.get("text", ""))
            if number in re.sub(r"\D", "", raw):
                return (word["x0"], word["y0"], word["x1"], word["y1"])
            if number in raw:
                return (word["x0"], word["y0"], word["x1"], word["y1"])
        return None

    def _locate_fragment(self, words, fragment):
        compact = re.sub(r"\D", "", fragment)
        return self._locate_number(words, compact)

    def _candidate(self, number, score, method, reason, box):
        box = box or (0.0, 0.0, 0.0, 0.0)
        return RecognitionCandidate(
            number=number,
            score=max(0, min(int(score), 100)),
            method=method,
            reason=reason,
            x0=float(box[0]),
            y0=float(box[1]),
            x1=float(box[2]),
            y1=float(box[3]),
        )
