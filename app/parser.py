"""Parser hội thoại: cắt văn bản dán vào thành các message kèm offset.

Hàm thuần túy, không đụng DB.
"""

import re
from dataclasses import dataclass, field

from alembic.environment import Literal

_MARKER_RE = re.compile(r"^@(me|chat):")
_FENCE_OPEN_RE = re.compile(r"^ {0,3}(`{3,}|~{3,})(.*)$")
_FENCE_CLOSE_RE = re.compile(r"^ {0,3}(`{3,}|~{3,})[ \t]*$")


@dataclass
class ParsedMessage:
    role: Literal["me", "chat"]
    content: str
    start_offset: int
    end_offset: int


@dataclass
class ParseWarning:
    code: str
    line: int | None  # đếm từ 1, trên normalized_text
    message: str


@dataclass
class ParseResult:
    normalized_text: str
    messages: list[ParsedMessage] = field(default_factory=list)
    warnings: list[ParseWarning] = field(default_factory=list)


@dataclass
class _Marker:
    role: Literal["me", "chat"]
    start: int  # offset đầu dòng chứa marker
    end: int  # offset ngay sau "@me:" / "@chat:"
    line: int


def normalize_newlines(text: str) -> str:
    return text.replace("\r\n", "\n").replace("\r", "\n")


def _line_of(text: str, offset: int) -> int:
    return text.count("\n", 0, offset) + 1


def _find_markers(text: str, warnings: list[ParseWarning]) -> list[_Marker]:
    """Duyệt từng dòng, theo dõi code fence, thu thập marker nằm ngoài fence."""
    markers: list[_Marker] = []
    fence_char: str | None = None
    fence_len = 0
    fence_line = 0

    offset = 0
    for line_no, line in enumerate(text.split("\n"), start=1):
        if fence_char is not None:
            m = _FENCE_CLOSE_RE.match(line)
            if m and m.group(1)[0] == fence_char and len(m.group(1)) >= fence_len:
                fence_char = None
        else:
            m = _FENCE_OPEN_RE.match(line)
            if m and not (m.group(1)[0] == "`" and "`" in m.group(2)):
                fence_char = m.group(1)[0]
                fence_len = len(m.group(1))
                fence_line = line_no
            else:
                mk = _MARKER_RE.match(line)
                if mk:
                    markers.append(
                        _Marker(mk.group(1), offset, offset + mk.end(), line_no)
                    )
        offset += len(line) + 1

    if fence_char is not None:
        warnings.append(
            ParseWarning(
                "unclosed_fence",
                fence_line,
                "Code fence mở ở dòng này nhưng không được đóng; "
                "marker phía sau bị coi là nội dung code.",
            )
        )
    return markers


def parse(text: str) -> ParseResult:
    normalized = normalize_newlines(text)
    result = ParseResult(normalized_text=normalized)
    warnings = result.warnings

    markers = _find_markers(normalized, warnings)

    if not markers:
        warnings.append(
            ParseWarning("no_marker", None, "Không tìm thấy marker @me: hoặc @chat:.")
        )
        return result

    # Chữ nằm trước marker đầu tiên: bỏ qua và cảnh báo.
    preamble = normalized[: markers[0].start]
    if preamble.strip():
        first = len(preamble) - len(preamble.lstrip())
        warnings.append(
            ParseWarning(
                "text_before_first_marker",
                _line_of(normalized, first),
                "Có chữ trước marker đầu tiên, phần này không thuộc message nào.",
            )
        )

    for i, mk in enumerate(markers):
        region_end = markers[i + 1].start if i + 1 < len(markers) else len(normalized)
        region = normalized[mk.end : region_end]
        stripped = region.strip()

        if stripped:
            start = mk.end + (len(region) - len(region.lstrip()))
            end = start + len(stripped)
        else:
            start = end = mk.end
            warnings.append(
                ParseWarning("empty_message", mk.line, "Marker không có nội dung.")
            )

        if i > 0 and markers[i - 1].role == mk.role:
            warnings.append(
                ParseWarning(
                    "consecutive_same_role",
                    mk.line,
                    f"Hai message @{mk.role} liên tiếp.",
                )
            )

        result.messages.append(ParsedMessage(mk.role, stripped, start, end))

    warnings.sort(key=lambda w: w.line or 0)
    return result