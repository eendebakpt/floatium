"""Type stubs for the compiled extension module floatium._ext."""

from typing import TypedDict

class _Info(TypedDict):
    patched: bool
    format_backend: str | None
    parse_backend: str | None
    available_format_backends: str
    available_parse_backends: str
    default_format_backend: str
    default_parse_backend: str

def install(
    format_backend: str | None = ...,
    parse_backend: str | None = ...,
) -> None: ...
def uninstall() -> None: ...
def is_patched() -> bool: ...
def info() -> _Info: ...
