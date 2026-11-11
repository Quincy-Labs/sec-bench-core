import json

import pytest
from fake_chain import FIXED_SRC, VULN_SRC, make_case

from sec_bench_core import __version__
from sec_bench_core.cases import load_case
from sec_bench_core.grade import grade_detect, grade_exploit, grade_file, grade_patch


def detect(chain, case, **answer):
    return grade_detect(chain, case, json.dumps(answer), {})


# --- detect -----------------------------------------------------------------


def test_detect_strict_exact_match(chain, case):
    g = detect(chain, case, found=True, bug_class="access-control", location="vault::withdraw")
    assert g == {
        "correct": True,
        "lenient": True,
        "located": True,
        "class_ok": True,
        "class_exact": True,
        "location_ok": True,
        "found": True,
    }


def test_detect_strict_fully_qualified_location(chain, case):
    g = detect(chain, case, found=True, bug_class="access-control", location="pkg::Vault::withdraw")
    assert g["correct"] and g["lenient"]


def test_detect_lenient_only_right_module_wrong_function(chain, case):
    g = detect(chain, case, found=True, bug_class="access-control", location="vault::deposit")
    assert not g["correct"] and g["lenient"]
    assert g["class_ok"] and not g["location_ok"]


def test_detect_wrong_module_fails_both(chain, case):
    g = detect(chain, case, found=True, bug_class="access-control", location="pool::withdraw")
    assert not g["correct"] and not g["lenient"]


def test_detect_wrong_class_fails_both(chain, case):
    g = detect(chain, case, found=True, bug_class="arithmetic", location="vault::withdraw")
    assert not g["correct"] and not g["lenient"] and g["location_ok"]


def test_detect_unparseable(chain, case):
    g = grade_detect(chain, case, "I could not decide.", {})
    assert g["correct"] is False and g["lenient"] is False and g["reason"] == "unparseable"


def test_detect_clean_case(chain, clean_case):
    assert detect(chain, clean_case, found=False, bug_class="none")["correct"] is True
    g = detect(chain, clean_case, found=True, bug_class="arithmetic", location="vault::withdraw")
    assert g["correct"] is False and g["false_positive"] is True


# --- patch ------------------------------------------------------------------


def patch(chain, case, files):
    return grade_patch(chain, case, json.dumps({"files": files}), {})


def test_patch_pass(chain, case):
    g = patch(chain, case, {"src/vault.txt": FIXED_SRC})
    assert g["correct"] is True
    assert g["functional_ok"] and g["exploit_blocked"] is True
    assert g["functional_phase"] == "ok" and g["exploit_phase"] == "test_failed"


def test_patch_fails_functional_tests(chain, case):
    g = patch(chain, case, {"src/vault.txt": "ASSERT_OWNER only, function removed"})
    assert g["correct"] is False and g["functional_ok"] is False
    assert g["functional_phase"] == "test_failed"


def test_patch_fails_when_exploit_not_blocked(chain, case):
    g = patch(chain, case, {"src/vault.txt": VULN_SRC + "// cosmetic change\n"})
    assert g["correct"] is False and g["functional_ok"] is True and g["exploit_blocked"] is False


@pytest.mark.parametrize(
    "path",
    [
        "tests/exploit/steal.test",
        "tests/functional/basic.test",
        "../escape.txt",
        "src/../../x.txt",
        "/src/vault.txt",
        "/etc/passwd",
        "vault.txt",
        "C:\\src\\vault.txt",
        "",
    ],
)
def test_patch_rejects_unsafe_path(chain, case, path):
    # A model that overwrites the exploit test could "block" it trivially.
    g = patch(chain, case, {"src/vault.txt": FIXED_SRC, path: "forbid: nothing"})
    assert g["correct"] is False
    assert g["reason"].startswith("unsafe path(s) rejected")
    assert chain.calls == []  # nothing was built or run


def test_patch_never_modifies_case(chain, case):
    patch(chain, case, {"src/vault.txt": FIXED_SRC})
    assert (case.path / "vulnerable" / "src" / "vault.txt").read_text() == VULN_SRC


def test_patch_without_files(chain, case):
    g = grade_patch(chain, case, '{"files": {}}', {})
    assert g["correct"] is False and g["reason"] == "no files"


def test_patch_incomplete_when_exploit_withheld(chain, cases_root):
    c = load_case(make_case(cases_root, "FAKE-0009", with_exploit_test=False))
    g = patch(chain, c, {"src/vault.txt": FIXED_SRC})
    assert g["correct"] is False and g["incomplete"] is True and g["exploit_blocked"] is None


# --- exploit ----------------------------------------------------------------


def exploit(chain, case, test):
    return grade_exploit(chain, case, json.dumps({"test_file": test}), {})


def test_exploit_passes_on_vulnerable_fails_on_fixed(chain, case):
    g = exploit(chain, case, "require: NO_AUTH")
    assert g == {
        "correct": True,
        "passes_on_vulnerable": True,
        "fails_on_fixed": True,
        "vulnerable_phase": "ok",
        "fixed_phase": "test_failed",
    }
    assert [c[2] for c in chain.calls] == [{chain.exploit_filename: "require: NO_AUTH"}] * 2


def test_exploit_that_passes_on_both_is_wrong(chain, case):
    g = exploit(chain, case, "require: fn withdraw")
    assert g["correct"] is False
    assert g["passes_on_vulnerable"] is True and g["fails_on_fixed"] is False


def test_exploit_failing_on_vulnerable_is_wrong(chain, case):
    g = exploit(chain, case, "require: SOMETHING_ABSENT")
    assert g["correct"] is False and g["passes_on_vulnerable"] is False and g["fails_on_fixed"] is True


def test_exploit_that_does_not_build_is_wrong(chain, case):
    g = exploit(chain, case, "syntax error")
    assert g["correct"] is False and g["vulnerable_phase"] == "build_failed"


def test_exploit_missing_test(chain, case):
    g = grade_exploit(chain, case, '{"answer": "no"}', {})
    assert g["correct"] is False and g["reason"] == "no test"


# --- whole file -------------------------------------------------------------


def test_grade_file_adds_summary_with_core_version_and_chain(chain, case, cases_root, tmp_path):
    run = {
        "task": "detect",
        "model": "fake:m",
        "chain": "fake",
        "core_version": __version__,
        "outputs": [
            {
                "case": case.id,
                "sample": 0,
                "raw": json.dumps(
                    {"found": True, "bug_class": "access-control", "location": "vault::withdraw"}
                ),
            },
            {"case": case.id, "sample": 1, "raw": "nonsense"},
        ],
    }
    f = tmp_path / "r.json"
    f.write_text(json.dumps(run))
    grade_file(chain, f, cases_root)
    out = json.loads(f.read_text())
    assert out["summary"]["core_version"] == __version__ and out["summary"]["chain"] == "fake"
    assert out["summary"]["strict"] == {"cases": 1, "samples": 2, "best_at_k": 1.0, "mean": 0.5}
    assert out["outputs"][0]["grade"]["correct"] is True


def test_grade_file_refuses_other_chain(chain, cases_root, tmp_path):
    f = tmp_path / "r.json"
    f.write_text(json.dumps({"task": "detect", "model": "m", "chain": "other", "outputs": []}))
    with pytest.raises(ValueError, match="chain"):
        grade_file(chain, f, cases_root)


# --- located and bug_class_also (0.2.0) --------------------------------------


def test_located_ignores_class(chain, case):
    g = detect(chain, case, found=True, bug_class="arithmetic", location="vault::withdraw")
    assert g["located"] is True and g["correct"] is False


def test_located_false_for_wrong_function_and_unparseable(chain, case):
    assert (
        detect(chain, case, found=True, bug_class="access-control", location="vault::deposit")["located"]
        is False
    )
    assert grade_detect(chain, case, "??", {})["located"] is False


def test_clean_case_located_means_no_false_positive(chain, clean_case):
    assert detect(chain, clean_case, found=False, bug_class="none")["located"] is True
    assert detect(chain, clean_case, found=True, bug_class="arithmetic", location="a::b")["located"] is False


def test_bug_class_also_accepts_reviewed_alternative(chain, case):
    case.meta["bug_class_also"] = ["arithmetic"]
    g = detect(chain, case, found=True, bug_class="arithmetic", location="vault::withdraw")
    assert g["correct"] is True and g["class_ok"] is True and g["class_exact"] is False
    g = detect(chain, case, found=True, bug_class="none", location="vault::withdraw")
    assert g["correct"] is False


def test_bug_class_also_unhashable_claim(chain, case):
    case.meta["bug_class_also"] = ["arithmetic"]
    g = detect(chain, case, found=True, bug_class=["arithmetic"], location="vault::withdraw")
    assert g["correct"] is False


def test_summary_has_located_for_detect_only(chain, case, cases_root, tmp_path):
    raw = json.dumps({"found": True, "bug_class": "arithmetic", "location": "vault::withdraw"})
    run = {"task": "detect", "model": "m", "outputs": [{"case": case.id, "sample": 0, "raw": raw}]}
    f = tmp_path / "r.json"
    f.write_text(json.dumps(run))
    s = grade_file(chain, f, cases_root)["summary"]
    assert s["strict"]["mean"] == 0.0 and s["located"]["mean"] == 1.0
    assert s["splits"]["audit"]["located"]["best_at_k"] == 1.0
    assert s["per_case"][case.id]["located_any"] is True
    run = {"task": "exploit", "model": "m", "outputs": [{"case": case.id, "sample": 0, "raw": "{}"}]}
    f.write_text(json.dumps(run))
    s = grade_file(chain, f, cases_root)["summary"]
    assert "located" not in s and "located" not in s["splits"]["audit"]
