import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))

from fake_chain import FakeChain, make_case  # noqa: E402

from sec_bench_core.cases import load_case  # noqa: E402


@pytest.fixture
def chain():
    return FakeChain()


@pytest.fixture
def cases_root(tmp_path):
    root = tmp_path / "cases"
    root.mkdir()
    return root


@pytest.fixture
def case(cases_root):
    return load_case(make_case(cases_root))


@pytest.fixture
def clean_case(cases_root):
    path = make_case(cases_root, "FAKE-0002", source="clean", bug_class="none", bug_location="none")
    return load_case(path)
