"""``todo.v1.AuthService`` — registration, sign-in, sessions, and passwords.

Security decisions worth stating out loud, because they are the reason several of
these handlers look more convoluted than the happy path would need:

* **Sessions are opaque and server-side.** Revocation is an ``UPDATE``, not a
  blocklist, so signing out of a stolen session takes effect immediately.
* **Enumeration is not possible.** A wrong email and a wrong password produce the
  same error after the same amount of work, and ``RequestPasswordReset`` reports
  success whether or not the address exists.
* **Sign-in is rate limited per address**, counting attempts against addresses that
  do not exist too — otherwise an unknown address gets unlimited guesses.
* **Changing a password closes every other session**, because the point of the
  change is usually that someone else knows the old one.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from typing import Any, Final
from urllib.parse import quote

from connectrpc.request import RequestContext

from todo.v1 import auth_pb2
from todoapp.auth import passwords, tokens
from todoapp.auth.context import Principal, require_principal
from todoapp.auth.interceptor import SESSION_COOKIE_NAME
from todoapp.config import Settings
from todoapp.db.pool import Database
from todoapp.domain import enums, validation
from todoapp.errors import (
    Reason,
    already_exists,
    failed_precondition,
    invalid_argument,
    not_found,
    resource_exhausted,
    unauthenticated,
)
from todoapp.mail import Mailer, password_reset_email, verification_email
from todoapp.repositories import sessions as sessions_repo
from todoapp.repositories import users as users_repo
from todoapp.services import mappers

logger = logging.getLogger("todoapp.services.auth")

_PASSWORD_RESET_TABLE: Final = "password_reset_tokens"
_EMAIL_VERIFICATION_TABLE: Final = "email_verification_tokens"


class AuthService:
    """Implements the generated ``todo.v1.AuthService`` protocol."""

    def __init__(self, *, database: Database, settings: Settings, mailer: Mailer) -> None:
        """Wires the service to its collaborators."""
        self._db = database
        self._settings = settings
        self._mailer = mailer

    # --- Session plumbing ---------------------------------------------------

    @property
    def _session_ttl(self) -> timedelta:
        return timedelta(hours=self._settings.session_ttl_hours)

    def _set_session_cookie(self, ctx: RequestContext, token: str) -> None:
        """Attaches the session cookie to the response.

        ``HttpOnly`` keeps the token away from page scripts, and ``SameSite=Lax``
        lets the cookie ride along on top-level navigations (so following a
        verification link keeps you signed in) while still blocking it on
        cross-site subresource requests.
        """
        parts = [
            f"{SESSION_COOKIE_NAME}={token}",
            "Path=/",
            "HttpOnly",
            "SameSite=Lax",
            f"Max-Age={int(self._session_ttl.total_seconds())}",
        ]
        if self._settings.session_cookie_secure:
            parts.append("Secure")
        if self._settings.session_cookie_domain:
            parts.append(f"Domain={self._settings.session_cookie_domain}")
        ctx.response_headers().add("set-cookie", "; ".join(parts))

    def _clear_session_cookie(self, ctx: RequestContext) -> None:
        """Expires the session cookie."""
        parts = [f"{SESSION_COOKIE_NAME}=", "Path=/", "HttpOnly", "SameSite=Lax", "Max-Age=0"]
        if self._settings.session_cookie_secure:
            parts.append("Secure")
        ctx.response_headers().add("set-cookie", "; ".join(parts))

    def _client_ip(self, ctx: RequestContext) -> str | None:
        """Best-effort client address, for the session list and rate limiting.

        ``X-Forwarded-For`` is only consulted for its first hop and only because
        this service is expected to sit behind a proxy. It is never used for an
        authorization decision — a header a client controls could not be.
        """
        forwarded = ctx.request_headers().get("x-forwarded-for", "")
        if forwarded:
            first = forwarded.split(",")[0].strip()
            if first:
                return first
        address = ctx.client_address()
        return address.rsplit(":", 1)[0] if address else None

    async def _open_session(
        self, ctx: RequestContext, *, user_id: str, client: int
    ) -> tuple[dict[str, Any], str]:
        """Creates a session row and returns it with the raw token."""
        token, token_hash = tokens.new_session_token()
        client_label = enums.SESSION_CLIENT.to_db_or(
            client, enums.SESSION_CLIENT.from_db("web"), field="client"
        )
        async with self._db.transaction() as conn:
            row = await sessions_repo.create(
                conn,
                user_id=user_id,
                token_hash=token_hash,
                client=client_label,
                user_agent=ctx.request_headers().get("user-agent", ""),
                ip_address=self._client_ip(ctx),
                ttl=self._session_ttl,
            )
        self._set_session_cookie(ctx, token)
        return row, token

    # --- Registration and sign-in ------------------------------------------

    async def register(
        self, request: auth_pb2.RegisterRequest, ctx: RequestContext
    ) -> auth_pb2.RegisterResponse:
        """Creates an account, opens a session, and sends a verification email.

        The account starts as ``pending_verification`` and can be used immediately —
        confirming the address is required only for the RPCs that reach other
        people, such as sharing a list.
        """
        email = validation.email(request.credentials.email)
        display_name = validation.required_text(
            request.display_name, field="display_name", max_length=validation.MAX_DISPLAY_NAME
        )
        passwords.validate_strength(request.credentials.password, settings=self._settings)
        time_zone = validation.time_zone(request.time_zone)
        locale = enums.LOCALE.to_db_or(request.locale, enums.LOCALE.from_db("da"), field="locale")

        password_hash = passwords.hash_password(request.credentials.password)

        async with self._db.transaction() as conn:
            if await users_repo.email_exists(conn, email):
                raise already_exists(
                    Reason.ERROR_REASON_EMAIL_ALREADY_REGISTERED,
                    "email address is already registered",
                    field="credentials.email",
                )
            row = await users_repo.create(
                conn,
                email=email,
                password_hash=password_hash,
                display_name=display_name,
                role="member",
                status="pending_verification",
                locale=locale,
                time_zone=time_zone,
            )
            verify_token, verify_hash = tokens.new_verification_token()
            await sessions_repo.create_one_time_token(
                conn,
                _EMAIL_VERIFICATION_TABLE,
                user_id=str(row["id"]),
                token_hash=verify_hash,
                ttl=timedelta(hours=self._settings.email_verification_ttl_hours),
            )

        await self._send_verification(
            email=email, name=display_name, locale=locale, token=verify_token
        )
        session_row, token = await self._open_session(
            ctx, user_id=str(row["id"]), client=request.client
        )
        return auth_pb2.RegisterResponse(
            user=mappers.user(row),
            session=mappers.session(session_row, current_session_id=str(session_row["id"])),
            token=token,
        )

    async def login(
        self, request: auth_pb2.LoginRequest, ctx: RequestContext
    ) -> auth_pb2.LoginResponse:
        """Exchanges email and password for a session.

        Every failure path takes roughly the same time and returns the same error,
        so the endpoint reveals nothing about which addresses are registered.
        """
        email = validation.email(request.credentials.email)
        ip_address = self._client_ip(ctx)

        async with self._db.connection() as conn:
            window_start = datetime.now(UTC) - timedelta(
                minutes=self._settings.login_attempt_window_minutes
            )
            failures = await sessions_repo.recent_failed_login_count(
                conn, email=email, since=window_start
            )
            if failures >= self._settings.login_max_attempts:
                await sessions_repo.record_login_attempt(
                    conn, email=email, succeeded=False, ip_address=ip_address
                )
                raise resource_exhausted(
                    Reason.ERROR_REASON_RATE_LIMITED,
                    "too many failed sign-in attempts",
                    metadata={
                        "retry_after_minutes": str(self._settings.login_attempt_window_minutes)
                    },
                )
            credentials = await users_repo.get_credentials_by_email(conn, email)

        if credentials is None:
            # Spend the same Argon2 time as a real verification would, so a wrong
            # address is indistinguishable from a wrong password.
            passwords.dummy_verify()
            await self._record_failure(email, ip_address)
            raise unauthenticated(
                Reason.ERROR_REASON_INVALID_CREDENTIALS, "email or password is incorrect"
            )

        if not passwords.verify_password(
            credentials["password_hash"], request.credentials.password
        ):
            await self._record_failure(email, ip_address)
            raise unauthenticated(
                Reason.ERROR_REASON_INVALID_CREDENTIALS, "email or password is incorrect"
            )

        self._reject_unusable_status(credentials["status"])

        user_id = str(credentials["id"])
        if passwords.needs_rehash(credentials["password_hash"]):
            # The password is in hand and correct — the only moment an upgrade to
            # stronger parameters is possible.
            await self._upgrade_hash(user_id, request.credentials.password)

        async with self._db.connection() as conn:
            await sessions_repo.record_login_attempt(
                conn, email=email, succeeded=True, ip_address=ip_address
            )
            await users_repo.touch_last_seen(conn, user_id)
            row = await users_repo.get_by_id(conn, user_id)
        assert row is not None

        session_row, token = await self._open_session(ctx, user_id=user_id, client=request.client)
        return auth_pb2.LoginResponse(
            user=mappers.user(row),
            session=mappers.session(session_row, current_session_id=str(session_row["id"])),
            token=token,
        )

    async def logout(
        self, request: auth_pb2.LogoutRequest, ctx: RequestContext
    ) -> auth_pb2.LogoutResponse:
        """Revokes the calling session and clears the cookie."""
        del request  # No fields; the session comes from the request context.
        principal = require_principal(ctx)
        async with self._db.transaction() as conn:
            await sessions_repo.revoke(
                conn, session_id=principal.session_id, user_id=principal.user_id
            )
        self._clear_session_cookie(ctx)
        return auth_pb2.LogoutResponse()

    async def refresh_session(
        self, request: auth_pb2.RefreshSessionRequest, ctx: RequestContext
    ) -> auth_pb2.RefreshSessionResponse:
        """Rotates the calling session's token and extends its lifetime.

        Rotating on every refresh bounds how long a leaked token stays useful, even
        when the leak is never noticed.
        """
        del request
        principal = require_principal(ctx)
        token, token_hash = tokens.new_session_token()
        async with self._db.transaction() as conn:
            row = await sessions_repo.rotate(
                conn,
                session_id=principal.session_id,
                token_hash=token_hash,
                ttl=self._session_ttl,
            )
        if row is None:
            raise unauthenticated(Reason.ERROR_REASON_SESSION_EXPIRED, "session is no longer valid")
        self._set_session_cookie(ctx, token)
        return auth_pb2.RefreshSessionResponse(
            session=mappers.session(row, current_session_id=str(row["id"])), token=token
        )

    # --- Passwords ----------------------------------------------------------

    async def change_password(
        self, request: auth_pb2.ChangePasswordRequest, ctx: RequestContext
    ) -> auth_pb2.ChangePasswordResponse:
        """Replaces the caller's password and closes every session but a fresh one.

        The current password is required even though the caller is already
        authenticated: it is what stops someone with a borrowed session from locking
        the real owner out.
        """
        principal = require_principal(ctx)
        passwords.validate_strength(request.new_password, settings=self._settings)

        async with self._db.connection() as conn:
            credentials = await users_repo.get_credentials_by_email(conn, principal.email)
        if credentials is None:
            raise not_found(Reason.ERROR_REASON_USER_NOT_FOUND, "account no longer exists")
        if not passwords.verify_password(credentials["password_hash"], request.current_password):
            raise invalid_argument(
                Reason.ERROR_REASON_CURRENT_PASSWORD_INCORRECT,
                "current password is incorrect",
                field="current_password",
            )

        new_hash = passwords.hash_password(request.new_password)
        async with self._db.transaction() as conn:
            await users_repo.set_password_hash(conn, principal.user_id, new_hash)
            await sessions_repo.revoke_all_for_user(conn, principal.user_id)

        # Every session is gone, including this one, so issue a replacement rather
        # than signing the caller out of the app they are standing in.
        session_row, token = await self._open_session(
            ctx, user_id=principal.user_id, client=enums.SESSION_CLIENT.from_db("web")
        )
        return auth_pb2.ChangePasswordResponse(
            session=mappers.session(session_row, current_session_id=str(session_row["id"])),
            token=token,
        )

    async def request_password_reset(
        self, request: auth_pb2.RequestPasswordResetRequest, ctx: RequestContext
    ) -> auth_pb2.RequestPasswordResetResponse:
        """Emails a reset link, if the address belongs to an account.

        Always reports success. Reporting "no such account" here would turn the
        endpoint into an address-enumeration oracle for anyone who wanted one.
        """
        del ctx
        email = validation.email(request.email)
        ttl = timedelta(minutes=self._settings.password_reset_ttl_minutes)

        async with self._db.transaction() as conn:
            credentials = await users_repo.get_credentials_by_email(conn, email)
            if credentials is None:
                logger.info("password reset requested for unknown address")
                return auth_pb2.RequestPasswordResetResponse()
            token, token_hash = tokens.new_reset_token()
            await sessions_repo.create_one_time_token(
                conn,
                _PASSWORD_RESET_TABLE,
                user_id=str(credentials["id"]),
                token_hash=token_hash,
                ttl=ttl,
            )

        locale = (
            enums.LOCALE.to_db(request.locale, field="locale")
            if request.locale
            else credentials["locale"]
        )
        await self._mailer.send(
            password_reset_email(
                to=email,
                name=credentials["display_name"],
                # The web app keeps the locale in a cookie rather than in the path,
                # so the language travels as a query parameter the page honours.
                link=(
                    f"{self._settings.web_base_url}/reset-password"
                    f"?token={quote(token)}&lang={locale}"
                ),
                locale=locale,
                minutes=self._settings.password_reset_ttl_minutes,
            )
        )
        return auth_pb2.RequestPasswordResetResponse()

    async def reset_password(
        self, request: auth_pb2.ResetPasswordRequest, ctx: RequestContext
    ) -> auth_pb2.ResetPasswordResponse:
        """Sets a new password from an emailed token and closes every session.

        Consuming the token and revoking sessions happen in one transaction, so a
        link cannot be redeemed twice and cannot half-apply.
        """
        del ctx
        passwords.validate_strength(request.new_password, settings=self._settings)
        if not request.token:
            raise invalid_argument(
                Reason.ERROR_REASON_FIELD_REQUIRED, "token is required", field="token"
            )
        new_hash = passwords.hash_password(request.new_password)

        async with self._db.transaction() as conn:
            user_id = await sessions_repo.consume_one_time_token(
                conn, _PASSWORD_RESET_TABLE, tokens.hash_token(request.token)
            )
            if user_id is None:
                raise invalid_argument(
                    Reason.ERROR_REASON_TOKEN_INVALID,
                    "reset link is invalid or has expired",
                    field="token",
                )
            await users_repo.set_password_hash(conn, str(user_id), new_hash)
            await sessions_repo.revoke_all_for_user(conn, str(user_id))
        return auth_pb2.ResetPasswordResponse()

    # --- Email verification -------------------------------------------------

    async def verify_email(
        self, request: auth_pb2.VerifyEmailRequest, ctx: RequestContext
    ) -> auth_pb2.VerifyEmailResponse:
        """Confirms an address and promotes the account to ``active``."""
        del ctx
        if not request.token:
            raise invalid_argument(
                Reason.ERROR_REASON_FIELD_REQUIRED, "token is required", field="token"
            )
        async with self._db.transaction() as conn:
            user_id = await sessions_repo.consume_one_time_token(
                conn, _EMAIL_VERIFICATION_TABLE, tokens.hash_token(request.token)
            )
            if user_id is None:
                raise invalid_argument(
                    Reason.ERROR_REASON_TOKEN_INVALID,
                    "verification link is invalid or has expired",
                    field="token",
                )
            row = await users_repo.mark_email_verified(conn, str(user_id))
        if row is None:
            raise not_found(Reason.ERROR_REASON_USER_NOT_FOUND, "account no longer exists")
        return auth_pb2.VerifyEmailResponse(user=mappers.user(row))

    async def resend_verification_email(
        self, request: auth_pb2.ResendVerificationEmailRequest, ctx: RequestContext
    ) -> auth_pb2.ResendVerificationEmailResponse:
        """Issues a fresh verification link for the caller's address.

        Any previous unused link is invalidated first, so only the newest one works.
        """
        del request
        principal = require_principal(ctx)
        if principal.email_verified:
            raise failed_precondition(
                Reason.ERROR_REASON_VALIDATION_FAILED, "email address is already verified"
            )
        token, token_hash = tokens.new_verification_token()
        async with self._db.transaction() as conn:
            await sessions_repo.create_one_time_token(
                conn,
                _EMAIL_VERIFICATION_TABLE,
                user_id=principal.user_id,
                token_hash=token_hash,
                ttl=timedelta(hours=self._settings.email_verification_ttl_hours),
            )
        await self._send_verification(
            email=principal.email,
            name=principal.display_name,
            locale=principal.locale,
            token=token,
        )
        return auth_pb2.ResendVerificationEmailResponse()

    # --- Session management -------------------------------------------------

    async def list_sessions(
        self, request: auth_pb2.ListSessionsRequest, ctx: RequestContext
    ) -> auth_pb2.ListSessionsResponse:
        """Lists the caller's live sessions, flagging the current one."""
        del request
        principal = require_principal(ctx)
        async with self._db.connection() as conn:
            rows = await sessions_repo.list_for_user(conn, principal.user_id)
        return auth_pb2.ListSessionsResponse(
            sessions=[mappers.session(row, current_session_id=principal.session_id) for row in rows]
        )

    async def revoke_session(
        self, request: auth_pb2.RevokeSessionRequest, ctx: RequestContext
    ) -> auth_pb2.RevokeSessionResponse:
        """Revokes one of the caller's own sessions."""
        principal = require_principal(ctx)
        session_id = validation.uuid_value(request.id, field="id")
        async with self._db.transaction() as conn:
            revoked = await sessions_repo.revoke(
                conn, session_id=session_id, user_id=principal.user_id
            )
        if not revoked:
            raise not_found(Reason.ERROR_REASON_SESSION_NOT_FOUND, "session not found")
        if session_id == principal.session_id:
            self._clear_session_cookie(ctx)
        return auth_pb2.RevokeSessionResponse()

    # --- Internals ----------------------------------------------------------

    def _reject_unusable_status(self, status: str) -> None:
        """Rejects sign-in for an account that exists but may not hold a session."""
        if status in enums.SIGNIN_ALLOWED_STATUSES:
            return
        reason = (
            Reason.ERROR_REASON_ACCOUNT_SUSPENDED
            if status == "suspended"
            else Reason.ERROR_REASON_ACCOUNT_DEACTIVATED
        )
        raise failed_precondition(reason, f"account is {status}")

    async def _record_failure(self, email: str, ip_address: str | None) -> None:
        async with self._db.connection() as conn:
            await sessions_repo.record_login_attempt(
                conn, email=email, succeeded=False, ip_address=ip_address
            )

    async def _upgrade_hash(self, user_id: str, password: str) -> None:
        """Re-hashes a correct password with the current Argon2 parameters."""
        try:
            async with self._db.transaction() as conn:
                await users_repo.set_password_hash(conn, user_id, passwords.hash_password(password))
        except Exception:
            # A failed upgrade must not fail the sign-in it happened during.
            logger.exception("failed to upgrade password hash for user %s", user_id)

    async def _send_verification(self, *, email: str, name: str, locale: str, token: str) -> None:
        """Sends the verification email, tolerating a delivery failure.

        Registration has already committed by this point. Failing the RPC would
        leave the caller believing no account exists while one does, so a bad
        mailer is logged and the user can ask for a new link.
        """
        try:
            await self._mailer.send(
                verification_email(
                    to=email,
                    name=name,
                    link=(
                        f"{self._settings.web_base_url}/verify-email"
                        f"?token={quote(token)}&lang={locale}"
                    ),
                    locale=locale,
                    hours=self._settings.email_verification_ttl_hours,
                )
            )
        except Exception:
            logger.exception("failed to send verification email")


def principal_or_none(ctx: RequestContext) -> Principal | None:
    """Re-exported for handlers that treat anonymous access as valid."""
    from todoapp.auth.context import current_principal

    return current_principal(ctx)
