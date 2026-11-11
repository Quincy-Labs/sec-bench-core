"""sec_bench_core: shared harness for AI smart-contract security benchmarks."""

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("sec-bench-core")
except PackageNotFoundError:  # running from a source tree without install
    __version__ = "0.2.0"
