"""Parse JSON from model output: code fences, surrounding prose, truncation."""

from __future__ import annotations

import json
import re


def _repair_partial(s: str) -> str | None:
    """Best-effort close of unclosed strings/arrays/objects in truncated JSON."""
    stack: list[str] = []
    in_str = False
    esc = False
    for ch in s:
        if in_str:
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == '"':
                in_str = False
            continue
        if ch == '"':
            in_str = True
        elif ch in "{[":
            stack.append(ch)
        elif ch in "}]":
            if not stack:
                return None
            stack.pop()
    if in_str:
        s = s + '"'
    s = s.rstrip()
    if s.endswith(","):
        s = s[:-1]
    s = re.sub(r":\s*$", "", s)
    s = re.sub(r'\s*,\s*"[^"]*"\s*$', "", s)
    while stack:
        s = s + ("}" if stack.pop() == "{" else "]")
    return s


def parse_json(raw: str) -> tuple[dict | None, str | None]:
    """Parse model output that may be wrapped in prose or code fences.

    Returns (dict_or_None, reason); reason is None on success.
    """
    if not raw or not raw.strip():
        return None, "empty"
    text = raw.strip()
    if "\u010a" in text or "\u0120" in text:
        # Some servers (LM Studio + devstral) return undecoded BPE merge tokens
        # in the content field: U+010A (newline merge) and U+0120 (space merge),
        # which breaks JSON parsing. Decode before attempting.
        text = text.replace("\u010a", "\n").replace("\u0120", " ")
    if "```" in text:
        m = re.search(r"```[\w+-]*\s*(.*?)```", text, re.S)
        if m:
            text = m.group(1).strip()
    candidates = [text]
    first, last = text.find("{"), text.rfind("}")
    if first != -1 and last > first:
        candidates.append(text[first : last + 1])
    for cand in candidates:
        try:
            value = json.loads(cand)
            return (value, None) if isinstance(value, dict) else (None, "not an object")
        except json.JSONDecodeError:
            pass
    if first != -1:
        repaired = _repair_partial(text[first:])
        if repaired:
            try:
                value = json.loads(repaired)
                if isinstance(value, dict):
                    return value, None
            except json.JSONDecodeError:
                pass
    return None, "unparseable"
