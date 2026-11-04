"""The core must stay chain-independent: no "move" or "sui" in sec_bench_core/.

Text is split into tokens on anything that is not a letter or digit (so "_"
splits too): sui_version, run_move_tests and foo.move are caught; ordinary
words that merely contain the letters, such as "remove", are not.
"""

import re
from pathlib import Path

import sec_bench_core

BANNED = {"move", "sui"}


def test_core_has_no_chain_words():
    root = Path(sec_bench_core.__file__).parent
    hits = []
    for f in sorted(root.rglob("*.py")):
        for n, line in enumerate(f.read_text().splitlines(), 1):
            for tok in re.split(r"[^A-Za-z0-9]+", line):
                # also split camelCase (SuiChain -> Sui, Chain)
                for part in re.findall(r"[A-Z]?[a-z0-9]+|[A-Z]+(?![a-z])", tok):
                    if part.lower() in BANNED:
                        hits.append(f"{f.relative_to(root)}:{n}: {line.strip()}")
    assert hits == [], "chain-specific words in core:\n" + "\n".join(hits)


def test_guard_catches_examples():
    sample = "sui_version run_move_tests x.move SuiChain MOVE remove movement"
    toks = [
        p.lower()
        for t in re.split(r"[^A-Za-z0-9]+", sample)
        for p in re.findall(r"[A-Z]?[a-z0-9]+|[A-Z]+(?![a-z])", t)
    ]
    assert toks.count("sui") == 2 and toks.count("move") == 3
