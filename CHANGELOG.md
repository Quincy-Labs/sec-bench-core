# Changelog

Minor versions can change grades or summary numbers; patch versions cannot.

## 0.3.0 (2026-11-10)

- detect grades gain `pinpointed` and `subject_ok` for cases with `bug_subject`
  (and `pinpointed` for clean cases): right function and the answer's `subject`
  names the account, object, argument or variable at fault. Summaries, splits,
  per-case results and the leaderboard report it over those cases only.
- `sec_bench_core.subject`: deterministic subject matching (one identifier after
  normalizing paths, method calls and filler words).
- `check-case` validates `bug_subject`.

## 0.2.0 (2026-11-10)

- detect grades gain `located` (right module and function, whatever the class)
  and `class_exact`. Summaries and splits gain `located`; per-case results gain
  `located_any`. The leaderboard shows Located best@k and mean for detect.
- `meta.yaml` `bug_class_also`: reviewed alternative classes that also count as
  the right class. `check-case` validates it. Strict and lenient scores can
  change on cases that set it.
- `sec_bench_core.classes`: `LABEL_PRINCIPLE` and `class_guide()` for detect prompts.

## 0.1.0 (2026-11-04)

- Harness extracted from sui-sec-bench: adapters, run loop, JSON repair,
  grading, leak check, check-case, leaderboard, `sec-bench` CLI, Chain protocol.
