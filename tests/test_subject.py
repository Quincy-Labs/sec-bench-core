import pytest

from sec_bench_core.subject import normalize_subject, subject_matches


@pytest.mark.parametrize(
    ("subject", "want"),
    [
        ("config", "config"),
        ("`config`", "config"),
        ("Config", "config"),
        ("the config account", "config"),
        ("ctx.accounts.config", "config"),
        ("ctx.accounts.authority.key()", "authority"),
        ("vault::Config", "config"),
        ("authority (signer)", "authority"),
        ("config: AccountView", "config"),
        ("&mut config", "config"),
        ("pub_keys argument", "pub_keys"),
        ("config, vault", None),
        ("config and vault", None),
        ("", None),
        ("the account", None),
        (None, None),
        (["config"], None),
    ],
)
def test_normalize(subject, want):
    assert normalize_subject(subject) == want


def test_matches_any_accepted_name_case_insensitively():
    assert subject_matches("ctx.accounts.Config", ["config", "cfg"])
    assert subject_matches("cfg", ["Config", "cfg"])
    assert not subject_matches("vault", ["config"])
    assert not subject_matches("config, vault", ["config", "vault"])
