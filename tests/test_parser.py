from app.parser import ParseResult, parse


def assert_offsets(result: ParseResult) -> None:
    """Bất biến 1.15: full_text[start:end] == content cho mọi message."""
    for m in result.messages:
        assert result.normalized_text[m.start_offset : m.end_offset] == m.content


def codes(result: ParseResult) -> list[str]:
    return [w.code for w in result.warnings]


def test_basic_two_messages_and_offsets():
    r = parse("@me: Hi\n@chat: Hello")

    assert [(m.role, m.content, m.start_offset, m.end_offset) for m in r.messages] == [
        ("me", "Hi", 5, 7),
        ("chat", "Hello", 15, 20),
    ]
    assert r.warnings == []
    assert_offsets(r)


def test_marker_inside_code_fence_is_ignored():
    text = (
        "@me: Viết cho mình đoạn in ra chuỗi mẫu\n"
        "@chat: Đây:\n"
        "```python\n"
        'print("ví dụ")\n'
        "@me: dòng này nằm trong code, không phải lượt nói\n"
        "```\n"
        "@me: Cảm ơn\n"
    )
    r = parse(text)

    assert [m.role for m in r.messages] == ["me", "chat", "me"]
    assert "@me: dòng này nằm trong code" in r.messages[1].content
    assert r.warnings == []
    assert_offsets(r)


def test_crlf_gives_same_result_as_lf():
    lf = "@me: Một\ndòng hai\n@chat: Trả lời\n```bash\nls\n```\n"
    crlf = lf.replace("\n", "\r\n")

    a, b = parse(lf), parse(crlf)

    assert "\r" not in b.normalized_text
    assert b.normalized_text == a.normalized_text
    assert b.messages == a.messages
    assert_offsets(b)


def test_lone_cr_is_normalized():
    r = parse("@me: a\r@chat: b")

    assert r.normalized_text == "@me: a\n@chat: b"
    assert [m.content for m in r.messages] == ["a", "b"]
    assert_offsets(r)


def test_emoji_offsets():
    r = parse("@me: 😀 hi 🎉\n@chat: ok 👍")

    assert [m.content for m in r.messages] == ["😀 hi 🎉", "ok 👍"]
    assert_offsets(r)


def test_unclosed_fence_swallows_later_markers_and_warns():
    text = "@me: Chạy lệnh nào?\n@chat: Dùng:\n```bash\nuv run pytest\n@me: Cảm ơn"
    r = parse(text)

    assert len(r.messages) == 2
    assert "@me: Cảm ơn" in r.messages[1].content
    assert codes(r) == ["unclosed_fence"]
    assert r.warnings[0].line == 3
    assert_offsets(r)


def test_decorators_are_not_markers():
    text = (
        "@me: Cho ví dụ fixture\n"
        "@chat: Đây:\n"
        "@pytest.fixture\n"
        "def session(): ...\n"
        "@dataclass\n"
        "class A: ...\n"
    )
    r = parse(text)

    assert [m.role for m in r.messages] == ["me", "chat"]
    assert "@pytest.fixture" in r.messages[1].content
    assert_offsets(r)


def test_marker_must_be_lowercase_and_at_line_start():
    r = parse("@me: ok\n@Me: không phải\n  @chat: thụt đầu dòng\nvăn bản @chat: giữa dòng")

    assert len(r.messages) == 1
    assert_offsets(r)


def test_no_marker():
    r = parse("chỉ là văn bản thường\nkhông có marker")

    assert r.messages == []
    assert codes(r) == ["no_marker"]
    assert r.normalized_text == "chỉ là văn bản thường\nkhông có marker"


def test_empty_text():
    r = parse("")

    assert r.messages == []
    assert codes(r) == ["no_marker"]


def test_consecutive_same_role():
    r = parse("@me: một\n@me: hai\n@chat: ba\n@chat: bốn")

    assert codes(r) == ["consecutive_same_role", "consecutive_same_role"]
    assert [w.line for w in r.warnings] == [2, 4]
    assert len(r.messages) == 4
    assert_offsets(r)


def test_text_before_first_marker_is_ignored_with_warning():
    r = parse("\n\nlời mở đầu\n@me: hỏi\n@chat: đáp")

    assert [m.content for m in r.messages] == ["hỏi", "đáp"]
    assert codes(r) == ["text_before_first_marker"]
    assert r.warnings[0].line == 3
    assert "lời mở đầu" in r.normalized_text  # vẫn còn trong full_text
    assert_offsets(r)


def test_empty_message():
    r = parse("@me:\n@chat: đáp")

    assert r.messages[0].content == ""
    assert r.messages[0].start_offset == r.messages[0].end_offset
    assert codes(r) == ["empty_message"]
    assert_offsets(r)


def test_tilde_fence_not_closed_by_backticks():
    text = "@me: a\n@chat: b\n~~~\n```\n@me: trong fence\n~~~\n@me: c"
    r = parse(text)

    assert [m.role for m in r.messages] == ["me", "chat", "me"]
    assert "@me: trong fence" in r.messages[1].content
    assert r.warnings == []
    assert_offsets(r)


def test_fence_not_closed_by_shorter_or_labeled_line():
    text = "@me: a\n@chat: b\n````\n```\n```python\n@me: vẫn trong fence\n````\n@me: c"
    r = parse(text)

    assert [m.role for m in r.messages] == ["me", "chat", "me"]
    assert "@me: vẫn trong fence" in r.messages[1].content
    assert r.warnings == []
    assert_offsets(r)


def test_inner_whitespace_and_indent_preserved_outer_stripped():
    text = "@me:   \n\n  x\n    indented\n\n\n@chat: y"
    r = parse(text)

    assert r.messages[0].content == "x\n    indented"
    assert_offsets(r)


def test_marker_value_on_next_line():
    r = parse("@chat:\nDùng lệnh:\n```bash\nls\n```")

    assert r.messages[0].content.startswith("Dùng lệnh:")
    assert r.messages[0].content.endswith("```")
    assert_offsets(r)


def test_command_preserved_verbatim():
    cmd = "uv run pre-commit run --files tests/test_health.py"
    r = parse(f"@me: cách chạy?\n@chat: Dùng:\n```bash\n{cmd}\n```")

    assert cmd in r.messages[1].content
    assert_offsets(r)