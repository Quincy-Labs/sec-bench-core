import yaml
from fake_chain import make_case

from sec_bench_core.cases import load_case
from sec_bench_core.check_case import check_case
from sec_bench_core.leak import scan_case, terms_for


def test_clean_case_has_no_leaks(chain, case):
    assert scan_case(chain, case) == []


def test_terms_include_chain_meta_and_bug_class(chain, case):
    case.meta["leak_terms"] = ["owner_cap"]
    terms = terms_for(chain, case)
    assert {"fakecoin", "owner_cap", "access-control", "access control", "vulnerab"} <= set(terms)


def test_leaks_found_in_sources_and_prompt(chain, cases_root):
    path = make_case(cases_root, prompt="Pay in FakeCoin.\n\n## Answer format\n\naudit exploit fix")
    (path / "vulnerable" / "src" / "vault.txt").write_text("fn withdraw()\n// TODO: access control\n")
    hits = scan_case(chain, load_case(path))
    assert ("vulnerable/src/vault.txt", 2, "todo", "// TODO: access control") in hits
    assert ("prompt.md", 1, "fakecoin", "Pay in FakeCoin.") in hits
    assert all(not (rel == "prompt.md" and line > 1) for rel, line, *_ in hits)  # answer format not scanned


def test_stems_and_whole_words(chain, cases_root):
    path = make_case(cases_root)
    (path / "vulnerable" / "src" / "vault.txt").write_text("vulnerability\nprefix\nbugs\n")
    hits = scan_case(chain, load_case(path))
    assert [(line, term) for _, line, term, _ in hits] == [(1, "vulnerab")]


def test_check_case_passes(chain, case):
    assert check_case(chain, case) == []


def test_check_case_reports_missing_chain_field_and_bad_exploit(chain, cases_root):
    path = make_case(cases_root)
    meta = yaml.safe_load((path / "meta.yaml").read_text())
    del meta["fake_version"]
    (path / "meta.yaml").write_text(yaml.safe_dump(meta))
    (path / "tests" / "exploit" / "steal.test").write_text("require: fn withdraw\n")  # passes on fixed too
    errors = check_case(chain, load_case(path))
    assert "missing field: fake_version" in errors
    assert any(e.startswith("exploit on fixed (must fail)") for e in errors)


def test_check_case_withheld_exploit_is_skipped(chain, cases_root, capsys):
    c = load_case(make_case(cases_root, with_exploit_test=False))
    assert check_case(chain, c) == []
    assert "[SKIP] no exploit test" in capsys.readouterr().out


def test_check_case_validates_bug_class_also(chain, cases_root):
    path = make_case(cases_root)
    meta = yaml.safe_load((path / "meta.yaml").read_text())
    meta["bug_class_also"] = ["arithmetic", "none", "access-control", "made-up"]
    (path / "meta.yaml").write_text(yaml.safe_dump(meta))
    errors = check_case(chain, load_case(path))
    bad = [e for e in errors if e.startswith("bug_class_also")]
    assert [e.split("'")[1] for e in bad] == ["none", "access-control", "made-up"]


def test_check_case_validates_bug_subject(chain, cases_root):
    path = make_case(cases_root)
    meta = yaml.safe_load((path / "meta.yaml").read_text())
    meta["bug_subject"] = ["withdraw", "not_in_sources", "two words"]
    (path / "meta.yaml").write_text(yaml.safe_dump(meta))
    errors = [e for e in check_case(chain, load_case(path)) if e.startswith("bug_subject")]
    assert errors == [
        "bug_subject 'not_in_sources' does not appear in the vulnerable sources",
        "bug_subject 'two words': must be one plain identifier",
    ]
