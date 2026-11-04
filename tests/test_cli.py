import json

import pytest
from fake_chain import make_case
from test_run import Boom, CountingAdapter

from sec_bench_core import __version__, cli
from sec_bench_core.config import ConfigError, import_chain, read_config


@pytest.fixture
def bench(tmp_path, monkeypatch):
    """A benchmark repo: bench.toml naming FakeChain, two cases, cwd set to it."""
    (tmp_path / "bench.toml").write_text('chain = "fake_chain:FakeChain"\n')
    (tmp_path / "cases").mkdir()
    make_case(tmp_path / "cases", "FAKE-0001")
    make_case(tmp_path / "cases", "FAKE-0002")
    monkeypatch.chdir(tmp_path)
    return tmp_path


def use_adapter(monkeypatch, adapter):
    monkeypatch.setattr(cli, "get_adapter", lambda spec: adapter)


def test_config_errors(tmp_path):
    with pytest.raises(ConfigError, match="not found"):
        read_config(tmp_path)
    (tmp_path / "bench.toml").write_text('chain = "no_colon"\n')
    with pytest.raises(ConfigError, match="ClassName"):
        read_config(tmp_path)
    with pytest.raises(ConfigError, match="cannot import"):
        import_chain("does_not_exist.mod:X")
    with pytest.raises(ConfigError, match="no class"):
        import_chain("fake_chain:Nope")
    with pytest.raises(ConfigError, match="missing: name"):
        import_chain("json:JSONDecoder")


def test_chain_module_loaded_from_bench_dir(tmp_path, monkeypatch):
    pkg = tmp_path / "my_bench"
    pkg.mkdir()
    (pkg / "__init__.py").write_text("")
    (pkg / "chain.py").write_text(
        "from fake_chain import FakeChain\n\nclass MyChain(FakeChain):\n    name = 'mine'\n"
    )
    (tmp_path / "bench.toml").write_text('chain = "my_bench.chain:MyChain"\ncases = "c"\n')
    from sec_bench_core.config import load_chain

    chain, cfg = load_chain(tmp_path)
    assert chain.name == "mine" and cfg.cases == tmp_path.resolve() / "c"


def test_missing_bench_toml_exits_2(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    assert cli.main(["leak-check", "--all"]) == 2
    assert "bench.toml" in capsys.readouterr().err


def test_cli_run_resume_grade_leaderboard(bench, monkeypatch):
    out = bench / "results" / "r.json"
    answer = json.dumps({"found": True, "bug_class": "access-control", "location": "vault::withdraw"})
    base = ["run", "--model", "fake:m", "--task", "detect", "--samples", "2", "--out", str(out)]

    use_adapter(monkeypatch, CountingAdapter(answer=answer, crash_after=3))
    with pytest.raises(Boom):
        cli.main(base)
    assert len(json.loads(out.read_text())["outputs"]) == 3

    adapter = CountingAdapter(answer=answer)
    use_adapter(monkeypatch, adapter)
    assert cli.main([*base, "--resume"]) == 0
    assert len(adapter.calls) == 1
    run = json.loads(out.read_text())
    assert len(run["outputs"]) == 4
    assert run["core_version"] == __version__ and run["chain"] == "fake"

    assert cli.main(["grade", str(out)]) == 0
    graded = json.loads(out.read_text())
    assert graded["summary"]["strict"]["mean"] == 1.0
    assert graded["summary"]["chain"] == "fake" and graded["summary"]["core_version"] == __version__

    assert cli.main(["leaderboard"]) == 0
    assert "| fake:m |" in (bench / "leaderboard" / "README.md").read_text()


def test_cli_resume_needs_existing_out(bench, monkeypatch):
    use_adapter(monkeypatch, CountingAdapter())
    with pytest.raises(SystemExit, match="needs --out"):
        cli.main(["run", "--model", "fake:m", "--task", "detect", "--resume"])
    with pytest.raises(SystemExit, match="does not exist"):
        cli.main(["run", "--model", "fake:m", "--task", "detect", "--resume", "--out", "nope.json"])


def test_cli_resume_refuses_other_task(bench, monkeypatch):
    out = bench / "r.json"
    use_adapter(monkeypatch, CountingAdapter())
    cli.main(["run", "--model", "fake:m", "--task", "detect", "--samples", "1", "--out", str(out)])
    with pytest.raises(SystemExit, match="task"):
        cli.main(["run", "--model", "fake:m", "--task", "patch", "--resume", "--out", str(out)])


def test_cli_leak_check_and_check_case(bench, capsys):
    assert cli.main(["leak-check", "--all"]) == 0
    assert cli.main(["check-case", "cases/FAKE-0001"]) == 0
    (bench / "cases" / "FAKE-0002" / "vulnerable" / "src" / "vault.txt").write_text("// FIXME\n")
    assert cli.main(["leak-check", "--all"]) == 1
    assert cli.main(["check-case", "--all"]) == 1
    out = capsys.readouterr().out
    assert "FAKE-0002: 1 leak(s)" in out and "== FAKE-0002 FAIL" in out
