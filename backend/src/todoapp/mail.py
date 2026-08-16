"""Outgoing transactional email.

Only two messages exist — verify your address, and reset your password — and both
are fully localized in Danish and English, because an email is as much part of the
product surface as a screen is.

Delivery is behind a :class:`Mailer` protocol. The default implementation logs the
message instead of sending it, which is the right behaviour for development: the
reset link lands in the terminal, and no real address is ever contacted by accident.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Final, Protocol

logger = logging.getLogger("todoapp.mail")


@dataclass(frozen=True, slots=True)
class Message:
    """One rendered email."""

    to: str
    subject: str
    body: str


class Mailer(Protocol):
    """Anything that can deliver a :class:`Message`."""

    async def send(self, message: Message) -> None:
        """Delivers ``message``, or raises if it cannot."""
        ...


class LoggingMailer:
    """Writes the message to the log instead of sending it.

    The body is logged in full, link included, so the development flow works
    end-to-end without an SMTP server.
    """

    async def send(self, message: Message) -> None:
        """Logs ``message`` at INFO."""
        logger.info(
            "email not sent (LoggingMailer): to=%s subject=%s\n%s",
            message.to,
            message.subject,
            message.body,
        )


# Subject and body per locale. Written natively in each language, in the product's
# voice — short, direct, no bureaucratic filler.
_VERIFY_EMAIL: Final[dict[str, tuple[str, str]]] = {
    "da": (
        "Bekræft din mail",
        "Hej {name}\n\n"
        "Klik her for at bekræfte din mail:\n{link}\n\n"
        "Linket holder i {hours} timer.\n\n"
        "Har du ikke oprettet en konto? Så kan du bare ignorere denne mail.",
    ),
    "en": (
        "Confirm your email",
        "Hi {name}\n\n"
        "Click here to confirm your email:\n{link}\n\n"
        "The link works for {hours} hours.\n\n"
        "Didn't sign up? You can ignore this email.",
    ),
}

_RESET_PASSWORD: Final[dict[str, tuple[str, str]]] = {
    "da": (
        "Nulstil din adgangskode",
        "Hej {name}\n\n"
        "Klik her for at vælge en ny adgangskode:\n{link}\n\n"
        "Linket holder i {minutes} minutter.\n\n"
        "Har du ikke bedt om det? Så gør ingenting — din adgangskode er uændret.",
    ),
    "en": (
        "Reset your password",
        "Hi {name}\n\n"
        "Click here to pick a new password:\n{link}\n\n"
        "The link works for {minutes} minutes.\n\n"
        "Didn't ask for this? Do nothing — your password is unchanged.",
    ),
}


def _template(table: dict[str, tuple[str, str]], locale: str) -> tuple[str, str]:
    """Picks the template for ``locale``, falling back to Danish."""
    return table.get(locale, table["da"])


def verification_email(*, to: str, name: str, link: str, locale: str, hours: int) -> Message:
    """Renders the address-confirmation email."""
    subject, body = _template(_VERIFY_EMAIL, locale)
    return Message(to=to, subject=subject, body=body.format(name=name, link=link, hours=hours))


def password_reset_email(*, to: str, name: str, link: str, locale: str, minutes: int) -> Message:
    """Renders the password-reset email."""
    subject, body = _template(_RESET_PASSWORD, locale)
    return Message(to=to, subject=subject, body=body.format(name=name, link=link, minutes=minutes))
