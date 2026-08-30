from __future__ import annotations

import unicodedata
from dataclasses import dataclass

import regex


HARD_MAX_WEIGHT = 280
TARGET_MIN_WEIGHT = 200
TARGET_MAX_WEIGHT = 250
TRANSFORMED_URL_WEIGHT = 23

URL_RE = regex.compile(r"(?i)\bhttps?://[^\s]+")
GRAPHEME_RE = regex.compile(r"\X")
EMOJI_CLUSTER_RE = regex.compile(
    r"\p{Extended_Pictographic}|\p{Regional_Indicator}|[#*0-9]\ufe0f?\u20e3"
)


class XTextValidationError(ValueError):
    pass


@dataclass(frozen=True)
class XTextMetrics:
    raw_length: int
    weighted_length: int


def normalize_text(text: str) -> str:
    return unicodedata.normalize("NFC", text).replace("\r\n", "\n").replace("\r", "\n").strip()


def _codepoint_weight(codepoint: int) -> int:
    if (
        0x0000 <= codepoint <= 0x10FF
        or 0x2000 <= codepoint <= 0x200D
        or 0x2010 <= codepoint <= 0x201F
        or 0x2032 <= codepoint <= 0x2037
    ):
        return 1
    return 2


def _segment_weight(segment: str) -> int:
    total = 0
    for cluster in GRAPHEME_RE.findall(segment):
        if EMOJI_CLUSTER_RE.search(cluster):
            total += 2
        else:
            total += sum(_codepoint_weight(ord(ch)) for ch in cluster)
    return total


def _weighted_units(normalized: str):
    cursor = 0
    for match in URL_RE.finditer(normalized):
        for cluster in GRAPHEME_RE.findall(normalized[cursor : match.start()]):
            yield cluster, _segment_weight(cluster)
        yield match.group(0), TRANSFORMED_URL_WEIGHT
        cursor = match.end()
    for cluster in GRAPHEME_RE.findall(normalized[cursor:]):
        yield cluster, _segment_weight(cluster)


def x_weighted_length(text: str) -> int:
    normalized = normalize_text(text)
    return sum(weight for _, weight in _weighted_units(normalized))


def metrics(text: str) -> XTextMetrics:
    normalized = normalize_text(text)
    return XTextMetrics(raw_length=len(normalized), weighted_length=x_weighted_length(normalized))


def validate_x_text(
    text: str,
    *,
    min_weight: int = TARGET_MIN_WEIGHT,
    max_weight: int = HARD_MAX_WEIGHT,
    label: str = "post",
) -> XTextMetrics:
    normalized = normalize_text(text)
    if not normalized:
        raise XTextValidationError(f"{label} is empty")
    result = metrics(normalized)
    if result.weighted_length < min_weight:
        raise XTextValidationError(
            f"{label} is too short: weighted={result.weighted_length}, minimum={min_weight}"
        )
    if result.weighted_length > max_weight:
        raise XTextValidationError(
            f"{label} exceeds X limit: weighted={result.weighted_length}, maximum={max_weight}"
        )
    return result


def truncate_to_weight(text: str, max_weight: int, suffix: str = "") -> str:
    normalized = normalize_text(text)
    suffix_weight = x_weighted_length(suffix) if suffix else 0
    if suffix_weight > max_weight:
        raise ValueError("suffix is longer than maximum weight")
    if x_weighted_length(normalized) <= max_weight:
        return normalized
    remaining = max_weight - suffix_weight
    output: list[str] = []
    used = 0
    for unit, weight in _weighted_units(normalized):
        if used + weight > remaining:
            break
        output.append(unit)
        used += weight
    return "".join(output).rstrip() + suffix


def append_verified_fillers(
    text: str,
    fillers: list[str],
    *,
    min_weight: int = TARGET_MIN_WEIGHT,
    max_weight: int = TARGET_MAX_WEIGHT,
) -> str:
    result = normalize_text(text)
    if x_weighted_length(result) >= min_weight:
        return result
    lines = result.splitlines()
    trailing_hashtag = lines[-1] if lines and lines[-1].startswith("#") else ""
    body = "\n".join(lines[:-1] if trailing_hashtag else lines)
    for filler in fillers:
        candidate_body = f"{body}\n{normalize_text(filler)}"
        candidate = (
            f"{candidate_body}\n{trailing_hashtag}"
            if trailing_hashtag
            else candidate_body
        )
        if x_weighted_length(candidate) <= max_weight:
            result = candidate
            body = candidate_body
        if x_weighted_length(result) >= min_weight:
            return result
    return result
