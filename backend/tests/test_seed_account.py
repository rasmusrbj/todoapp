"""Choosing the demo account.

The seed asks for an email and a password rather than carrying a pair in the source,
so this file covers the part that can actually be wrong: the precedence between
flags, environment and prompt, the validation, and the refusal to invent a
credential when nobody is there to ask.

The prompt itself is `input()` and `getpass.getpass()` — stdlib plumbing. What is
worth testing is the retry loop and the validation around them, so those two are
patched rather than driven through a pseudo-terminal.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import pytest

from todoapp.db import seed


def args(**overrides: object) -> argparse.Namespace:
    """A parsed-args stand-in with everything defaulted to absent."""
    defaults: dict[str, object] = {
        "email": None,
        "password": None,
        "name": None,
        "credentials_file": None,
        "keep_existing": False,
    }
    return argparse.Namespace(**{**defaults, **overrides})


# --- Display names -----------------------------------------------------------


@pytest.mark.parametrize(
    ("email", "expected"),
    [
        ("rasmus.jensing@example.com", "Rasmus Jensing"),
        ("owner@example.com", "Owner"),
        ("first_last@example.com", "First Last"),
        ("dash-name@example.com", "Dash Name"),
        ("plus+tag@example.com", "Plus Tag"),
    ],
)
def test_display_name_is_derived_from_the_address(email: str, expected: str) -> None:
    assert seed._display_name_from(email) == expected


def test_display_name_never_ends_up_empty() -> None:
    """An address with nothing usable in front of the @ still needs a name."""
    assert seed._display_name_from("@example.com") == "Owner"


# --- Validation --------------------------------------------------------------


def test_valid_pair_passes() -> None:
    assert seed._check("owner@example.com", "a-long-enough-password") is None


def test_bad_email_is_reported() -> None:
    complaint = seed._check("not-an-email", "a-long-enough-password")
    assert complaint is not None
    assert "not a valid email" in complaint


def test_weak_password_is_reported_using_the_servers_own_rule() -> None:
    """The seed must not accept a password the API would later reject."""
    complaint = seed._check("owner@example.com", "short")
    assert complaint is not None
    assert "at least" in complaint


# --- Precedence --------------------------------------------------------------


def test_flags_win(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TODOAPP_DEMO_EMAIL", "env@example.com")
    monkeypatch.setenv("TODOAPP_DEMO_PASSWORD", "env-password-value")
    account = seed.resolve_account(args(email="flag@example.com", password="flag-password-value"))
    assert account.email == "flag@example.com"
    assert account.password == "flag-password-value"


def test_environment_is_used_when_flags_are_absent(monkeypatch: pytest.MonkeyPatch) -> None:
    """This is the path `make setup` and CI take — no terminal required."""
    monkeypatch.setenv("TODOAPP_DEMO_EMAIL", "env@example.com")
    monkeypatch.setenv("TODOAPP_DEMO_PASSWORD", "env-password-value")
    account = seed.resolve_account(args())
    assert account.email == "env@example.com"
    assert account.display_name == "Env"


def test_explicit_name_overrides_the_derived_one(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TODOAPP_DEMO_EMAIL", "env@example.com")
    monkeypatch.setenv("TODOAPP_DEMO_PASSWORD", "env-password-value")
    account = seed.resolve_account(args(name="Someone Else"))
    assert account.display_name == "Someone Else"


def test_invalid_credentials_from_the_environment_fail_loudly(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("TODOAPP_DEMO_EMAIL", "env@example.com")
    monkeypatch.setenv("TODOAPP_DEMO_PASSWORD", "tiny")
    with pytest.raises(SystemExit, match="at least"):
        seed.resolve_account(args())


def test_no_credentials_and_no_terminal_refuses(monkeypatch: pytest.MonkeyPatch) -> None:
    """The important one.

    A silent default here is how a known admin password reaches a real deployment,
    so with nothing supplied and no tty the seed must stop rather than guess.
    """
    monkeypatch.delenv("TODOAPP_DEMO_EMAIL", raising=False)
    monkeypatch.delenv("TODOAPP_DEMO_PASSWORD", raising=False)
    monkeypatch.setattr("sys.stdin.isatty", lambda: False)
    with pytest.raises(SystemExit, match="no terminal"):
        seed.resolve_account(args())


# --- The prompt --------------------------------------------------------------


def fake_prompt(monkeypatch: pytest.MonkeyPatch, emails: list[str], passwords: list[str]) -> None:
    """Feeds scripted answers to `input()` and `getpass()`."""
    monkeypatch.setattr("sys.stdin.isatty", lambda: True)
    monkeypatch.setattr("builtins.input", lambda *_: emails.pop(0))
    monkeypatch.setattr(seed.getpass, "getpass", lambda *_: passwords.pop(0))


def test_prompt_accepts_a_good_pair(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("TODOAPP_DEMO_EMAIL", raising=False)
    monkeypatch.delenv("TODOAPP_DEMO_PASSWORD", raising=False)
    fake_prompt(
        monkeypatch,
        emails=["typed@example.com"],
        passwords=["typed-password-here", "typed-password-here"],
    )
    account = seed.resolve_account(args())
    assert account == seed.DemoAccount("typed@example.com", "typed-password-here", "Typed")


def test_prompt_retries_a_mismatch_then_a_bad_email(monkeypatch: pytest.MonkeyPatch) -> None:
    """Three attempts, and the first two are the mistakes people actually make."""
    monkeypatch.delenv("TODOAPP_DEMO_EMAIL", raising=False)
    monkeypatch.delenv("TODOAPP_DEMO_PASSWORD", raising=False)
    fake_prompt(
        monkeypatch,
        emails=["first@example.com", "nonsense", "third@example.com"],
        passwords=[
            "one-password-here",
            "different-password",  # mismatch
            "fine-password-here",
            "fine-password-here",  # bad email
            "final-password-ok",
            "final-password-ok",  # accepted
        ],
    )
    account = seed.resolve_account(args())
    assert account.email == "third@example.com"


def test_prompt_gives_up_after_three_attempts(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("TODOAPP_DEMO_EMAIL", raising=False)
    monkeypatch.delenv("TODOAPP_DEMO_PASSWORD", raising=False)
    fake_prompt(
        monkeypatch,
        emails=["a@example.com"] * 3,
        passwords=["x", "y"] * 3,
    )
    with pytest.raises(SystemExit, match="three attempts"):
        seed.resolve_account(args())


# --- The credentials file ----------------------------------------------------


def test_credentials_file_is_written_owner_only(tmp_path: Path) -> None:
    """It holds a password, so it must not be world-readable."""
    target = tmp_path / "demo.env"
    seed.write_credentials(target, seed.DemoAccount("owner@example.com", "the-password", "Owner"))
    assert (target.stat().st_mode & 0o777) == 0o600

    body = target.read_text()
    assert "TODOAPP_DEMO_EMAIL=owner@example.com" in body
    assert "TODOAPP_DEMO_PASSWORD=the-password" in body
    # The header is what stops someone committing it by hand.
    assert "gitignored" in body


# --- Fixtures ----------------------------------------------------------------


def test_seed_users_puts_your_account_first_as_admin() -> None:
    account = seed.DemoAccount("owner@example.com", "pw", "Owner")
    users = seed.seed_users(account)
    assert users[0].key == "owner"
    assert users[0].email == "owner@example.com"
    assert users[0].role == "admin"
    assert [u.role for u in users[1:]] == ["member", "member"]


def test_collaborators_use_reserved_example_addresses() -> None:
    """RFC 2606 reserves example.com, so sample data cannot reach a real inbox."""
    for user in seed.COLLABORATORS:
        assert user.email.endswith("@example.com")


def test_no_personal_address_is_hardcoded() -> None:
    """Guards the reason this indirection exists at all."""
    source = Path(seed.__file__).read_text()
    assert "@happenings" not in source
