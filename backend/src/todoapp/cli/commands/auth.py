"""``todoapp auth …`` — sign in, sign out, sessions, passwords."""

from __future__ import annotations

import argparse
import getpass
from typing import Any

from todo.v1 import auth_pb2, user_pb2
from todoapp.cli import args as enum_args
from todoapp.cli import display, lookup, output
from todoapp.cli.client import Api, CliError, resolve_id


def register(subparsers: Any) -> None:
    """Adds the ``auth`` command group."""
    parser = subparsers.add_parser(
        "auth", help="sign in, sign out, and manage sessions", description="Authentication."
    )
    commands = parser.add_subparsers(
        dest="auth_command",
        metavar="<command>",
        required=True,
        parser_class=enum_args.LeafParser,
    )

    login = commands.add_parser("login", help="sign in and store the session")
    login.add_argument("--email", "-e", required=True, help="email address")
    login.add_argument(
        "--password",
        "-p",
        help="password; omit to be prompted, which keeps it out of shell history",
    )
    login.set_defaults(handler=_login)

    register_cmd = commands.add_parser("register", help="create an account and sign in")
    register_cmd.add_argument("--email", "-e", required=True)
    register_cmd.add_argument("--name", "-n", required=True, help="display name")
    register_cmd.add_argument("--password", "-p")
    register_cmd.add_argument(
        "--language",
        choices=enum_args.LOCALE.choices,
        default="da",
        help="the account's interface language (default: da)",
    )
    register_cmd.add_argument(
        "--time-zone", default="Europe/Copenhagen", help="IANA zone (default: Europe/Copenhagen)"
    )
    register_cmd.set_defaults(handler=_register)

    logout = commands.add_parser("logout", help="revoke this session")
    logout.set_defaults(handler=_logout)

    whoami = commands.add_parser("whoami", help="show the signed-in account")
    whoami.set_defaults(handler=_whoami)

    refresh = commands.add_parser("refresh", help="rotate this session's token")
    refresh.set_defaults(handler=_refresh)

    sessions = commands.add_parser("sessions", help="list this account's sessions")
    sessions.set_defaults(handler=_sessions)

    revoke = commands.add_parser("revoke-session", help="revoke a session by id")
    revoke.add_argument("id", help="session id, or a unique prefix of one")
    revoke.set_defaults(handler=_revoke_session)

    change = commands.add_parser("change-password", help="change the password")
    change.add_argument("--current", help="current password; omit to be prompted")
    change.add_argument("--new", help="new password; omit to be prompted")
    change.set_defaults(handler=_change_password)

    forgot = commands.add_parser("forgot-password", help="email a reset link")
    forgot.add_argument("--email", "-e", required=True)
    forgot.add_argument(
        "--language",
        choices=enum_args.LOCALE.choices,
        default="da",
        help="language for the reset email",
    )
    forgot.set_defaults(handler=_forgot_password)

    reset = commands.add_parser("reset-password", help="finish a reset with the emailed token")
    reset.add_argument("--token", "-t", required=True)
    reset.add_argument("--new", help="new password; omit to be prompted")
    reset.set_defaults(handler=_reset_password)

    verify = commands.add_parser("verify-email", help="confirm an address with its token")
    verify.add_argument("--token", "-t", required=True)
    verify.set_defaults(handler=_verify_email)

    resend = commands.add_parser("resend-verification", help="send a fresh confirmation link")
    resend.set_defaults(handler=_resend_verification)


def _ask_password(supplied: str | None, prompt: str) -> str:
    """Returns ``supplied``, or prompts without echoing.

    Raises:
        CliError: If nothing was entered.
    """
    password = supplied or getpass.getpass(prompt)
    if not password:
        raise CliError("A password is required.")
    return password


def _store_session(api: Api, token: str, email: str) -> None:
    api.config.token = token
    api.config.email = email
    api.config.save()


def _login(api: Api, options: argparse.Namespace) -> int:
    response = api.auth.login(
        auth_pb2.LoginRequest(
            credentials=auth_pb2.Credentials(
                email=options.email,
                password=_ask_password(options.password, f"Password for {options.email}: "),
            ),
            client=enum_args.SESSION_CLIENT.to_number("cli"),
        )
    )
    _store_session(api, response.token, response.user.email)
    if options.json:
        print(output.as_json(response))
    else:
        output.success(f"Signed in as {response.user.display_name} <{response.user.email}>")
        if not response.user.email_verified:
            output.warn("Your email is not confirmed yet — sharing lists stays disabled.")
    return 0


def _register(api: Api, options: argparse.Namespace) -> int:
    response = api.auth.register(
        auth_pb2.RegisterRequest(
            credentials=auth_pb2.Credentials(
                email=options.email,
                password=_ask_password(options.password, "Choose a password: "),
            ),
            display_name=options.name,
            locale=enum_args.LOCALE.to_number(options.language),
            time_zone=options.time_zone,
            client=enum_args.SESSION_CLIENT.to_number("cli"),
        )
    )
    _store_session(api, response.token, response.user.email)
    if options.json:
        print(output.as_json(response))
    else:
        output.success(f"Account created for {response.user.email}")
        print(output.paint("  Check the server log for the confirmation link.", "dim"))
    return 0


def _logout(api: Api, options: argparse.Namespace) -> int:
    api.auth.logout(auth_pb2.LogoutRequest(), headers=api.require_token())
    api.config.clear_token()
    api.config.save()
    if not options.json:
        output.success("Signed out.")
    return 0


def _whoami(api: Api, options: argparse.Namespace) -> int:
    response = api.users.get_current_user(
        user_pb2.GetCurrentUserRequest(), headers=api.require_token()
    )
    if options.json:
        print(output.as_json(response))
        return 0

    user = response.user
    locale = options.locale
    print(
        output.detail(
            [
                ("Name", user.display_name),
                ("Email", user.email),
                (
                    "Role",
                    display.enum_name(enum_args.USER_ROLE.value_name(user.role), locale=locale),
                ),
                (
                    "Status",
                    display.enum_name(enum_args.USER_STATUS.value_name(user.status), locale=locale),
                ),
                ("Confirmed", "yes" if user.email_verified else "no"),
                (
                    "Language",
                    display.enum_name(enum_args.LOCALE.value_name(user.locale), locale=locale),
                ),
                ("Time zone", user.time_zone),
                ("Own lists", str(user.stats.owned_list_count)),
                ("Shared with me", str(user.stats.shared_list_count)),
                ("Open tasks", str(user.stats.open_task_count)),
                ("Overdue", str(user.stats.overdue_task_count)),
                ("Server", api.config.base_url),
            ],
            title=user.display_name,
        )
    )
    return 0


def _refresh(api: Api, options: argparse.Namespace) -> int:
    response = api.auth.refresh_session(
        auth_pb2.RefreshSessionRequest(), headers=api.require_token()
    )
    api.config.token = response.token
    api.config.save()
    if options.json:
        print(output.as_json(response))
    else:
        expires = display.timestamp(response.session.expires_at, locale=options.locale)
        output.success(f"Session extended to {expires}")
    return 0


def _sessions(api: Api, options: argparse.Namespace) -> int:
    response = api.auth.list_sessions(auth_pb2.ListSessionsRequest(), headers=api.require_token())
    if options.json:
        print(output.as_json(response))
        return 0

    rows = [
        [
            output.short_id(session.id),
            "→" if session.is_current else "",
            display.enum_name(
                enum_args.SESSION_CLIENT.value_name(session.client), locale=options.locale
            ),
            output.truncate(session.user_agent or "—", 32),
            session.ip_address or "—",
            display.timestamp(session.last_used_at, locale=options.locale),
            display.relative_date(session.expires_at, locale=options.locale),
        ]
        for session in response.sessions
    ]
    print(
        output.table(
            ["ID", "", "CLIENT", "DEVICE", "IP", "LAST USED", "EXPIRES"],
            rows,
            empty_message="No active sessions.",
        )
    )
    return 0


def _revoke_session(api: Api, options: argparse.Namespace) -> int:
    session_id = resolve_id(options.id, lookup.sessions(api), kind="session")
    api.auth.revoke_session(
        auth_pb2.RevokeSessionRequest(id=session_id), headers=api.require_token()
    )
    if not options.json:
        output.success(f"Revoked session {output.short_id(session_id)}.")
    return 0


def _change_password(api: Api, options: argparse.Namespace) -> int:
    current = _ask_password(options.current, "Current password: ")
    new = _ask_password(options.new, "New password: ")
    response = api.auth.change_password(
        auth_pb2.ChangePasswordRequest(current_password=current, new_password=new),
        headers=api.require_token(),
    )
    # Every other session was closed, so adopt the replacement token.
    api.config.token = response.token
    api.config.save()
    if not options.json:
        output.success("Password changed. Every other session was signed out.")
    return 0


def _forgot_password(api: Api, options: argparse.Namespace) -> int:
    api.auth.request_password_reset(
        auth_pb2.RequestPasswordResetRequest(
            email=options.email, locale=enum_args.LOCALE.to_number(options.language)
        )
    )
    if not options.json:
        # Worded to match the API: success here says nothing about whether the
        # address exists.
        output.success("If that address has an account, a reset link is on its way.")
    return 0


def _reset_password(api: Api, options: argparse.Namespace) -> int:
    api.auth.reset_password(
        auth_pb2.ResetPasswordRequest(
            token=options.token, new_password=_ask_password(options.new, "New password: ")
        )
    )
    api.config.clear_token()
    api.config.save()
    if not options.json:
        output.success("Password reset. Sign in with the new one.")
    return 0


def _verify_email(api: Api, options: argparse.Namespace) -> int:
    response = api.auth.verify_email(auth_pb2.VerifyEmailRequest(token=options.token))
    if options.json:
        print(output.as_json(response))
    else:
        output.success(f"{response.user.email} confirmed.")
    return 0


def _resend_verification(api: Api, options: argparse.Namespace) -> int:
    api.auth.resend_verification_email(
        auth_pb2.ResendVerificationEmailRequest(), headers=api.require_token()
    )
    if not options.json:
        output.success("A fresh confirmation link is on its way.")
    return 0
