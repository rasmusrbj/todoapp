"""Registration, sign-in, sessions, and password flows."""

from __future__ import annotations

from tests.conftest import PASSWORD, CapturingMailer, Client, reason_of
from todoapp.db.pool import Database


async def test_health_and_readiness(client: Client) -> None:
    assert (await client.get("/healthz")).json() == {"status": "ok"}
    assert (await client.get("/readyz")).json()["database"] == "ok"


async def test_register_creates_pending_account_and_session(
    client: Client, mailer: CapturingMailer
) -> None:
    user = await client.register()

    assert user["status"] == "USER_STATUS_PENDING_VERIFICATION"
    assert user["role"] == "USER_ROLE_MEMBER"
    assert user["locale"] == "LOCALE_DA"
    # proto3 JSON omits false, so an unverified address has no key at all.
    assert "emailVerified" not in user
    assert client.token is not None and client.token.startswith("tds_")
    assert len(mailer.outbox) == 1
    assert mailer.outbox[0].subject == "Bekræft din mail"


async def test_register_email_is_normalised(client: Client) -> None:
    user = await client.register(email="  OWNER@Example.COM  ")
    assert user["email"] == "owner@example.com"


async def test_register_rejects_duplicate_email(client: Client) -> None:
    await client.register()
    result = await client.anon(
        "AuthService/Register",
        {
            "credentials": {"email": "owner@example.com", "password": PASSWORD},
            "displayName": "Nogen Anden",
        },
    )
    assert result["code"] == "already_exists"
    assert reason_of(result) == "ERROR_REASON_EMAIL_ALREADY_REGISTERED"


async def test_register_rejects_weak_passwords(client: Client) -> None:
    for password in ["kort", "password123", "aaaaaaaaaaaaaa"]:
        result = await client.anon(
            "AuthService/Register",
            {
                "credentials": {"email": f"x{len(password)}@example.com", "password": password},
                "displayName": "Svag",
            },
        )
        assert reason_of(result) == "ERROR_REASON_PASSWORD_TOO_WEAK", password


async def test_register_rejects_invalid_email_and_time_zone(client: Client) -> None:
    bad_email = await client.anon(
        "AuthService/Register",
        {"credentials": {"email": "not-an-email", "password": PASSWORD}, "displayName": "X"},
    )
    assert reason_of(bad_email) == "ERROR_REASON_INVALID_EMAIL"

    bad_zone = await client.anon(
        "AuthService/Register",
        {
            "credentials": {"email": "zone@example.com", "password": PASSWORD},
            "displayName": "X",
            "timeZone": "Mars/Olympus_Mons",
        },
    )
    assert reason_of(bad_zone) == "ERROR_REASON_INVALID_TIME_ZONE"


async def test_login_succeeds_and_wrong_password_does_not(client: Client) -> None:
    await client.register()
    assert "token" in await client.anon(
        "AuthService/Login",
        {"credentials": {"email": "owner@example.com", "password": PASSWORD}},
    )
    wrong = await client.anon(
        "AuthService/Login",
        {"credentials": {"email": "owner@example.com", "password": "helt-forkert-kode"}},
    )
    assert wrong["code"] == "unauthenticated"
    assert reason_of(wrong) == "ERROR_REASON_INVALID_CREDENTIALS"


async def test_login_does_not_disclose_whether_an_address_exists(client: Client) -> None:
    """An unknown address and a wrong password must be indistinguishable."""
    await client.register()
    wrong_password = await client.anon(
        "AuthService/Login",
        {"credentials": {"email": "owner@example.com", "password": "helt-forkert-kode"}},
    )
    unknown_address = await client.anon(
        "AuthService/Login",
        {"credentials": {"email": "findes-ikke@example.com", "password": "helt-forkert-kode"}},
    )
    assert wrong_password["code"] == unknown_address["code"]
    assert wrong_password["message"] == unknown_address["message"]
    assert reason_of(wrong_password) == reason_of(unknown_address)


async def test_login_is_rate_limited_per_address(client: Client) -> None:
    await client.register()
    codes = []
    for _ in range(12):
        result = await client.anon(
            "AuthService/Login",
            {"credentials": {"email": "owner@example.com", "password": "forkert-kode-igen"}},
        )
        codes.append(result["code"])
    assert "resource_exhausted" in codes, codes
    # The limit holds even once the right password is offered.
    blocked = await client.anon(
        "AuthService/Login",
        {"credentials": {"email": "owner@example.com", "password": PASSWORD}},
    )
    assert blocked["code"] == "resource_exhausted"
    assert reason_of(blocked) == "ERROR_REASON_RATE_LIMITED"


async def test_suspended_account_cannot_sign_in(client: Client, database: Database) -> None:
    await client.register()
    async with database.connection() as conn:
        await conn.execute(
            "UPDATE users SET status = 'suspended' WHERE email = %s", ("owner@example.com",)
        )
    result = await client.anon(
        "AuthService/Login",
        {"credentials": {"email": "owner@example.com", "password": PASSWORD}},
    )
    assert reason_of(result) == "ERROR_REASON_ACCOUNT_SUSPENDED"


async def test_suspended_account_cannot_use_an_existing_session(
    client: Client, database: Database
) -> None:
    """Suspension must take effect on the session already in the caller's hand."""
    await client.register()
    assert "user" in await client.call("UserService/GetCurrentUser")
    async with database.connection() as conn:
        await conn.execute(
            "UPDATE users SET status = 'suspended' WHERE email = %s", ("owner@example.com",)
        )
    result = await client.call("UserService/GetCurrentUser")
    assert reason_of(result) == "ERROR_REASON_ACCOUNT_SUSPENDED"


async def test_verify_email_activates_the_account(client: Client, mailer: CapturingMailer) -> None:
    await client.register()
    token = mailer.token_from_last_link()

    result = await client.anon("AuthService/VerifyEmail", {"token": token})
    assert result["user"]["status"] == "USER_STATUS_ACTIVE"
    assert result["user"]["emailVerified"] is True

    # One-time: the same link cannot be redeemed twice.
    again = await client.anon("AuthService/VerifyEmail", {"token": token})
    assert reason_of(again) == "ERROR_REASON_TOKEN_INVALID"


async def test_resend_verification_invalidates_the_previous_link(
    client: Client, mailer: CapturingMailer
) -> None:
    await client.register()
    first = mailer.token_from_last_link()
    await client.call("AuthService/ResendVerificationEmail")
    second = mailer.token_from_last_link()
    assert first != second

    stale = await client.anon("AuthService/VerifyEmail", {"token": first})
    assert reason_of(stale) == "ERROR_REASON_TOKEN_INVALID"
    assert "user" in await client.anon("AuthService/VerifyEmail", {"token": second})


async def test_verified_account_cannot_resend(client: Client, mailer: CapturingMailer) -> None:
    await client.register()
    await client.anon("AuthService/VerifyEmail", {"token": mailer.token_from_last_link()})
    result = await client.call("AuthService/ResendVerificationEmail")
    assert result["code"] == "failed_precondition"


async def test_logout_revokes_the_session(client: Client) -> None:
    await client.register()
    assert await client.call("AuthService/Logout") == {}
    result = await client.call("UserService/GetCurrentUser")
    assert result["code"] == "unauthenticated"


async def test_refresh_rotates_the_token(client: Client) -> None:
    await client.register()
    old_token = client.token
    result = await client.call("AuthService/RefreshSession")
    assert result["token"] != old_token

    # The rotated-away token must stop working immediately.
    client.token = old_token
    assert (await client.call("UserService/GetCurrentUser"))["code"] == "unauthenticated"
    client.token = result["token"]
    assert "user" in await client.call("UserService/GetCurrentUser")


async def test_change_password_closes_other_sessions(client: Client) -> None:
    await client.register()
    other_session = await client.anon(
        "AuthService/Login",
        {"credentials": {"email": "owner@example.com", "password": PASSWORD}},
    )

    result = await client.call(
        "AuthService/ChangePassword",
        {"currentPassword": PASSWORD, "newPassword": "en-helt-ny-kode-42"},
    )
    assert "token" in result

    # The other session is gone; the caller got a replacement.
    client.token = other_session["token"]
    assert (await client.call("UserService/GetCurrentUser"))["code"] == "unauthenticated"
    client.token = result["token"]
    assert "user" in await client.call("UserService/GetCurrentUser")

    # And the new password is the one that works.
    assert "token" in await client.anon(
        "AuthService/Login",
        {"credentials": {"email": "owner@example.com", "password": "en-helt-ny-kode-42"}},
    )


async def test_change_password_requires_the_current_one(client: Client) -> None:
    await client.register()
    result = await client.call(
        "AuthService/ChangePassword",
        {"currentPassword": "det-var-ikke-den", "newPassword": "en-helt-ny-kode-42"},
    )
    assert reason_of(result) == "ERROR_REASON_CURRENT_PASSWORD_INCORRECT"


async def test_password_reset_round_trip(client: Client, mailer: CapturingMailer) -> None:
    await client.register()
    mailer.outbox.clear()

    assert (
        await client.anon(
            "AuthService/RequestPasswordReset",
            {"email": "owner@example.com", "locale": "LOCALE_EN"},
        )
        == {}
    )
    assert mailer.outbox[-1].subject == "Reset your password"
    token = mailer.token_from_last_link()

    assert (
        await client.anon(
            "AuthService/ResetPassword", {"token": token, "newPassword": "nulstillet-kode-99"}
        )
        == {}
    )
    assert "token" in await client.anon(
        "AuthService/Login",
        {"credentials": {"email": "owner@example.com", "password": "nulstillet-kode-99"}},
    )
    # Single use.
    assert (
        reason_of(
            await client.anon(
                "AuthService/ResetPassword", {"token": token, "newPassword": "endnu-en-kode-99"}
            )
        )
        == "ERROR_REASON_TOKEN_INVALID"
    )


async def test_password_reset_for_unknown_address_reports_success_and_sends_nothing(
    client: Client, mailer: CapturingMailer
) -> None:
    """The endpoint must not become an address-enumeration oracle."""
    assert (
        await client.anon("AuthService/RequestPasswordReset", {"email": "findes-ikke@example.com"})
        == {}
    )
    assert mailer.outbox == []


async def test_reset_password_still_enforces_the_strength_policy(
    client: Client, mailer: CapturingMailer
) -> None:
    await client.register()
    await client.anon("AuthService/RequestPasswordReset", {"email": "owner@example.com"})
    result = await client.anon(
        "AuthService/ResetPassword",
        {"token": mailer.token_from_last_link(), "newPassword": "kort"},
    )
    assert reason_of(result) == "ERROR_REASON_PASSWORD_TOO_WEAK"


async def test_sessions_can_be_listed_and_revoked(client: Client) -> None:
    await client.register()
    current = client.token
    other = await client.anon(
        "AuthService/Login",
        {"credentials": {"email": "owner@example.com", "password": PASSWORD}},
    )

    listed = await client.call("AuthService/ListSessions")
    assert len(listed["sessions"]) == 2
    assert sum(1 for s in listed["sessions"] if s.get("isCurrent")) == 1

    target = next(s for s in listed["sessions"] if not s.get("isCurrent"))
    assert await client.call("AuthService/RevokeSession", {"id": target["id"]}) == {}

    client.token = other["token"]
    assert (await client.call("UserService/GetCurrentUser"))["code"] == "unauthenticated"
    client.token = current
    assert len((await client.call("AuthService/ListSessions"))["sessions"]) == 1


async def test_cannot_revoke_another_users_session(client: Client, second_client: Client) -> None:
    await client.register()
    theirs = (await second_client.call("AuthService/ListSessions"))["sessions"][0]
    result = await client.call("AuthService/RevokeSession", {"id": theirs["id"]})
    assert reason_of(result) == "ERROR_REASON_SESSION_NOT_FOUND"


async def test_garbage_token_is_simply_unauthenticated(client: Client) -> None:
    client.token = "tds_this-was-never-issued"
    assert (await client.call("UserService/GetCurrentUser"))["code"] == "unauthenticated"
