"""
Normalize DRF error responses so auth and permission failures share one JSON shape.

Output (401/403 only): {"detail": "<human-readable message>", "code": "<machine identifier>"}.
Validation (400) and other statuses are left as DRF returns them.

`drf_exception_handler` already turns APIExceptions into `response.data` dicts, but the
inner `detail` field varies by exception source. We flatten those into plain strings.

Typical `response.data` shapes before normalization:

- **NotAuthenticated / PermissionDenied** — `{"detail": "..."}` or `detail` as a list of
  ErrorDetail (DRF). Optional sibling `code` may be missing; we fall back to the
  exception's `code` / `default_code`.

- **Simple JWT (invalid/expired token)** — often `{"detail": ErrorDetail(...), "code":
  "token_not_valid"}` or `detail` as a list of token error dicts; we take the first
  message and prefer JWT's `code` when present.

- **Our AuthenticationFailed (inactive user)** — `{"detail": "User is inactive."}` with
  `exc.code == "user_inactive"`; sibling `code` in data may be absent.

- **Edge cases** — `detail` nested as `{"detail": {...}, "code": ...}` (nested dict), or
  top-level `messages` (list); see `_normalize_detail_and_code` below.
"""

from typing import Any

from rest_framework import status
from rest_framework.exceptions import APIException
from rest_framework.views import exception_handler as drf_exception_handler


def _as_text(value: Any) -> str:
    """Coerce ErrorDetail and similar objects to a plain string (`.string` if present)."""
    if value is None:
        return ""
    if hasattr(value, "string"):
        return str(value.string)
    return str(value)


def _normalize_detail_and_code(exc: APIException, data: Any) -> tuple[str, str]:
    """
    Derive (detail, code) for the unified error JSON.

    `data` is `response.data` from DRF's exception handler: usually a dict, sometimes
    non-dict for odd cases. Branches handle string / list / nested-dict `detail`, plus
    optional top-level `code` and `messages`.
    """
    code = getattr(exc, "code", None) or getattr(type(exc), "default_code", None) or "error"
    code = _as_text(code)

    if not isinstance(data, dict):
        return _as_text(data) or _as_text(exc), code

    raw_detail = data.get("detail")
    extra_code = data.get("code")

    # Nested dict (e.g. some JWT payloads)
    if isinstance(raw_detail, dict):
        inner = raw_detail.get("detail") or raw_detail.get("message") or raw_detail
        nested_code = raw_detail.get("code")
        return _as_text(inner), _as_text(nested_code or extra_code or code)

    if isinstance(raw_detail, list) and raw_detail:
        first = raw_detail[0]
        return _as_text(first), _as_text(extra_code or code)

    if raw_detail is not None:
        return _as_text(raw_detail), _as_text(extra_code or code)

    messages = data.get("messages")
    if isinstance(messages, list) and messages:
        return _as_text(messages[0]), code

    return _as_text(exc), code


def custom_exception_handler(exc: Any, context: dict) -> Any:
    response = drf_exception_handler(exc, context)
    if response is None:
        return None

    if not isinstance(exc, APIException):
        return response

    if response.status_code == status.HTTP_401_UNAUTHORIZED:
        detail, code = _normalize_detail_and_code(exc, response.data)
        response.data = {"detail": detail, "code": code}

    elif response.status_code == status.HTTP_403_FORBIDDEN:
        detail, code = _normalize_detail_and_code(exc, response.data)
        response.data = {"detail": detail, "code": code}

    return response
