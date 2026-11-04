from sec_bench_core.jsonparse import _repair_partial, parse_json


def test_plain_object():
    assert parse_json('{"found": true}') == ({"found": True}, None)


def test_code_fence_with_language_tag():
    for tag in ("json", "rust", "solidity", ""):
        raw = f'Here you go:\n```{tag}\n{{"a": 1}}\n```\nthanks'
        assert parse_json(raw) == ({"a": 1}, None), tag


def test_prose_around_json():
    raw = 'I think the answer is {"found": false, "bug_class": "none"} and that is all.'
    assert parse_json(raw) == ({"found": False, "bug_class": "none"}, None)


def test_empty_and_unparseable():
    assert parse_json("") == (None, "empty")
    assert parse_json("   ") == (None, "empty")
    assert parse_json("no json here") == (None, "unparseable")


def test_not_an_object():
    assert parse_json("[1, 2]") == (None, "not an object")


def test_truncated_string_is_repaired():
    raw = '{"files": {"src/a.txt": "line one\\nline tw'
    out, why = parse_json(raw)
    assert why is None
    assert out == {"files": {"src/a.txt": "line one\nline tw"}}


def test_truncated_after_key_and_comma():
    out, why = parse_json('{"found": true, "bug_class": "arithmetic", "location":')
    assert why is None and out == {"found": True, "bug_class": "arithmetic"}
    out, why = parse_json('{"found": true, "x": [1, 2,')
    assert why is None and out == {"found": True, "x": [1, 2]}


def test_dangling_key_dropped():
    out, why = parse_json('{"found": true, "bug_class"')
    assert why is None and out == {"found": True}


def test_repair_handles_escaped_quotes():
    assert _repair_partial('{"a": "say \\"hi') == '{"a": "say \\"hi"}'


def test_repair_rejects_unbalanced_close():
    assert _repair_partial('{"a": 1}}') is None


def test_bpe_merge_tokens_are_decoded():
    raw = '{ĊĠ"a":Ġ"xĠy"}'
    assert parse_json(raw) == ({"a": "x y"}, None)
