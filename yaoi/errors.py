"""Typed failures — one place for each cause and its exit status."""

from __future__ import annotations


class YaoiError(Exception):
    code = 1
    hint = ""

    def __init__(self, message: str, hint: str | None = None):
        super().__init__(message)
        self.message = message
        if hint is not None:
            self.hint = hint


class SourceError(YaoiError):
    code = 2
    hint = "The site layout may have changed. Keep the URL and try again later."


class AuthError(YaoiError):
    code = 3
    hint = "Reader keys were rejected. Run `yaoi keys refresh`."


class SealError(AuthError):
    hint = "The sealed payload could not be read. Refresh the reader keys."


class NetworkError(YaoiError):
    code = 1


class ExportError(YaoiError):
    code = 1
    hint = "The downloaded images are still on disk."


class SelectionError(YaoiError):
    code = 2


class ConfigError(YaoiError):
    code = 2


class Cancelled(YaoiError):
    code = 130
    hint = ""
