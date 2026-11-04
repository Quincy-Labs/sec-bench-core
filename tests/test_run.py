import json

import pytest
from fake_chain import make_case

from sec_bench_core import __version__
from sec_bench_core.adapters.base import Completion
from sec_bench_core.cases import load_cases
from sec_bench_core.run import build_messages, new_run, prompt_sha256, run_task


class Boom(Exception):
    pass


class CountingAdapter:
    """Returns a fixed answer; can be told to crash after n calls."""

    def __init__(self, answer='{"found": false}', crash_after=None):
        self.answer = answer
        self.crash_after = crash_after
        self.calls = []
        self.conversations = []

    def complete(self, system, user, max_tokens=0):
        if self.crash_after is not None and len(self.calls) >= self.crash_after:
            raise Boom("simulated crash")
        self.calls.append((system, user))
        return Completion(text=self.answer, latency_s=0.01, completion_tokens=5)

    def complete_conversation(self, messages, max_tokens=0):
        self.conversations.append([m["content"] for m in messages])
        return Completion(text=self.answer, latency_s=0.01)


def make_run(chain, task="detect", samples=3, **kw):
    return new_run(
        chain,
        model="fake:m",
        task=task,
        samples=samples,
        agentic=kw.get("agentic", False),
        iters=kw.get("iters", 5),
        thinking=None,
        max_tokens=100,
    )


def test_prompts_use_chain_answer_format_and_classes(chain, case):
    system, user = build_messages(chain, "detect", case)
    assert "access-control, arithmetic, none" in system
    assert "old format" not in user and "classes: access-control, arithmetic, none" in user
    assert user.startswith("Review the vault package.")
    assert "// File: src/vault.txt" in user


def test_new_run_records_core_version_and_chain(chain):
    run = make_run(chain)
    assert run["core_version"] == __version__ and run["chain"] == "fake"
    assert run["prompt_sha256"] == prompt_sha256(chain, "detect")


def test_samples_and_resume(chain, cases_root, tmp_path):
    make_case(cases_root, "FAKE-0001")
    make_case(cases_root, "FAKE-0002")
    cases = load_cases(cases_root)
    out = tmp_path / "results" / "r.json"

    # First attempt crashes after 4 of 6 samples; the file holds the first 4.
    run = make_run(chain, samples=3)
    with pytest.raises(Boom):
        run_task(chain, CountingAdapter(crash_after=4), run, cases, out, samples=3, max_tokens=100)
    saved = json.loads(out.read_text())
    assert [(o["case"], o["sample"]) for o in saved["outputs"]] == [
        ("FAKE-0001", 0),
        ("FAKE-0001", 1),
        ("FAKE-0001", 2),
        ("FAKE-0002", 0),
    ]

    # Resume from the file: only the 2 missing samples are requested.
    adapter = CountingAdapter()
    resumed = run_task(chain, adapter, saved, cases, out, samples=3, max_tokens=100)
    assert len(adapter.calls) == 2
    final = json.loads(out.read_text())
    assert sorted((o["case"], o["sample"]) for o in final["outputs"]) == [
        (c, i) for c in ("FAKE-0001", "FAKE-0002") for i in range(3)
    ]
    assert final["run_id"] == run["run_id"] == resumed["run_id"]
    assert final["chain"] == "fake" and final["core_version"] == __version__

    # Resuming a complete file does nothing.
    adapter = CountingAdapter()
    run_task(chain, adapter, final, cases, out, samples=3, max_tokens=100)
    assert adapter.calls == []


def test_resume_refuses_other_chain(chain, case, tmp_path):
    run = make_run(chain)
    run["chain"] = "other"
    with pytest.raises(ValueError, match="chain"):
        run_task(chain, CountingAdapter(), run, [case], tmp_path / "r.json", samples=1, max_tokens=1)


def test_skips_cases_without_task(chain, cases_root, tmp_path):
    make_case(cases_root, "FAKE-0003", tasks=("patch",))
    adapter = CountingAdapter()
    run_task(
        chain, adapter, make_run(chain), load_cases(cases_root), tmp_path / "r.json", samples=2, max_tokens=1
    )
    assert adapter.calls == []


def test_agentic_stops_when_solved(chain, case, tmp_path):
    adapter = CountingAdapter(answer=json.dumps({"test_file": "require: NO_AUTH"}))
    run = make_run(chain, task="exploit", samples=1, agentic=True, iters=3)
    run_task(chain, adapter, run, [case], tmp_path / "r.json", samples=1, max_tokens=1, agentic=True, iters=3)
    rec = run["outputs"][0]
    assert rec["agentic"] is True and len(rec["iterations"]) == 1 and rec["iterations"][0]["solved"]
    assert [c[2] for c in chain.calls] == [{chain.exploit_filename: "require: NO_AUTH"}] * 2


def test_agentic_feedback_never_shows_fixed_package(chain, case, tmp_path):
    adapter = CountingAdapter(answer=json.dumps({"test_file": "require: fn withdraw"}))  # passes on both
    run = make_run(chain, task="exploit", samples=1, agentic=True, iters=2)
    run_task(chain, adapter, run, [case], tmp_path / "r.json", samples=1, max_tokens=1, agentic=True, iters=2)
    feedback = adapter.conversations[1][-1]
    assert "also PASSED on the fixed package" in feedback
    assert "ASSERT_OWNER" not in feedback  # the fix itself is never leaked


def test_agentic_retry_template(chain, case, tmp_path):
    adapter = CountingAdapter(answer="not json")
    run = make_run(chain, task="exploit", samples=1, agentic=True, iters=2)
    run_task(chain, adapter, run, [case], tmp_path / "r.json", samples=1, max_tokens=1, agentic=True, iters=2)
    assert adapter.conversations[1][-1].startswith("Your last answer could not be graded (unparseable).")
    assert '{"test_file":' in adapter.conversations[1][-1]
