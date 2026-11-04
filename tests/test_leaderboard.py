import json

from sec_bench_core.grade import grade_run
from sec_bench_core.leaderboard import at_limit, build, frac, table


def test_helpers():
    outs = [{"grade": {"correct": True}, "completion_tokens": 99}, {"grade": {}, "completion_tokens": 3}]
    assert frac(outs) == "1/2"
    assert at_limit(outs, 100) == 1
    assert table(["a", "b"], [[1, 2]]) == "| a | b |\n| --- | --- |\n| 1 | 2 |"


def test_build_from_graded_files(chain, case, cases_root, tmp_path):
    results = tmp_path / "results"
    results.mkdir()
    good = json.dumps({"found": True, "bug_class": "access-control", "location": "vault::withdraw"})
    run = {
        "task": "detect",
        "model": "fake:m",
        "chain": "fake",
        "max_tokens": 100,
        "outputs": [
            {"case": case.id, "sample": 0, "raw": good, "completion_tokens": 10},
            {"case": case.id, "sample": 1, "raw": "?", "completion_tokens": 100},
        ],
    }
    grade_run(chain, run, cases_root, verbose=False)
    (results / "graded.json").write_text(json.dumps(run))
    (results / "ungraded.json").write_text(json.dumps({"task": "detect", "model": "x", "outputs": []}))

    data = build(results, tmp_path / "lb")
    assert len(data["rows"]) == 1
    r = data["rows"][0]
    assert r["strict"]["best_at_k"] == 1.0 and r["strict"]["mean"] == 0.5 and r["at_token_limit"] == 1
    md = (tmp_path / "lb" / "README.md").read_text()
    assert "## detect" in md and "| fake:m | single-shot | 1 | 2 | 100% | 50% |" in md
    assert json.loads((tmp_path / "lb" / "leaderboard.json").read_text())["chains"] == ["fake"]
