"""
Unified JSON error responses for DRF APIExceptions.

**Shape**

- Every handled error includes **`detail`** (string) and **`code`** (string).
- **400** validation / parse-style errors may also include **`fields`**: an object mapping
  field names (including dotted paths for nested data) to lists of string messages.
  Omit `fields` when there are no per-field messages to report (rare).

**Examples**

```json
{"detail": "Authentication credentials were not provided.", "code": "not_authenticated"}
{"detail": "Invalid input.", "code": "validation_error", "fields": {"email": ["Enter a valid email."]}}
```

**Sources**

`drf_exception_handler` builds `response.data` in different shapes (strings, ErrorDetail,
lists, nested dicts). We normalize those into the contract above.

- **401 / 403** — NotAuthenticated, PermissionDenied, AuthenticationFailed, JWT errors;
  see `_normalize_detail_and_code`.
- **400** — `ValidationError` (serializers): flatten to `fields` + summary `detail`.
  `ParseError` and other 400s: `detail` + `code`, and `fields` when the payload is a dict.
- **404 / 405 / 429** — same `detail` + `code` pattern as 401/403.

Django **`Http404`** / **`PermissionDenied`** are converted to a response inside DRF's
handler, but the original `exc` may still be the Django type. `_coerce_to_api_exception`
wraps those so **404/403** bodies still get `detail` + `code`.
"""

from typing import Any

from rest_framework import status
from rest_framework.exceptions import (
    APIException,
    NotFound,
    PermissionDenied as DRFPermissionDenied,
    ValidationError,
)
from rest_framework.views import exception_handler as drf_exception_handler


def _coerce_to_api_exception(exc: Any) -> APIException | None:
    """DRF's handler may build a response from Django's Http404 / PermissionDenied while `exc` stays non-API."""
    if isinstance(exc, APIException):
        return exc
    from django.core.exceptions import PermissionDenied as DjangoPermissionDenied
    from django.http import Http404

    if isinstance(exc, Http404):
        return NotFound(*(exc.args) or ("Not found.",))
    if isinstance(exc, DjangoPermissionDenied):
        return DRFPermissionDenied(*(exc.args) or ())
    return None


def _as_text(value: Any) -> str:
    """Coerce ErrorDetail and similar objects to a plain string (`.string` if present)."""
    if value is None:
        return ""
    if hasattr(value, "string"):
        return str(value.string)
    return str(value)


def _normalize_detail_and_code(exc: APIException, data: Any) -> tuple[str, str]:
    """
    Derive (detail, code) for errors that are not full validation dicts.

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


def _flatten_field_errors(key: str, val: Any) -> dict[str, list[str]]:
    if isinstance(val, list):
        return {key: [_as_text(x) for x in val]}
    if isinstance(val, dict):
        out: dict[str, list[str]] = {}
        for nk, nv in val.items():
            compound = f"{key}.{nk}"
            out.update(_flatten_field_errors(compound, nv))
        return out
    return {key: [_as_text(val)]}


def _flatten_validation_errors(data: dict) -> dict[str, list[str]]:
    out: dict[str, list[str]] = {}
    for k, v in data.items():
        out.update(_flatten_field_errors(k, v))
    return out


def _pick_validation_summary(fields: dict[str, list[str]]) -> str:
    if "non_field_errors" in fields and fields["non_field_errors"]:
        return fields["non_field_errors"][0]
    for _key, messages in fields.items():
        if messages:
            return messages[0]
    return "Validation failed."


def _build_400_payload(exc: ValidationError, data: Any) -> dict[str, Any]:
    default_code = _as_text(
        getattr(exc, "code", None)
        or getattr(type(exc), "default_code", None)
        or "invalid"
    )
    if not isinstance(data, dict):
        detail, code = _normalize_detail_and_code(exc, data)
        return {"detail": detail, "code": code}

    fields = _flatten_validation_errors(data)
    if not fields:
        detail, code = _normalize_detail_and_code(exc, data)
        return {"detail": detail, "code": code}

    detail = _pick_validation_summary(fields)

    if set(fields.keys()) == {"detail"}:
        return {"detail": detail, "code": default_code}

    return {"detail": detail, "code": "validation_error", "fields": fields}


def custom_exception_handler(exc: Any, context: dict) -> Any:
    response = drf_exception_handler(exc, context)
    if response is None:
        return None

    status_code = response.status_code
    data = response.data

    if status_code in [
        status.HTTP_401_UNAUTHORIZED,
        status.HTTP_403_FORBIDDEN,
        status.HTTP_404_NOT_FOUND,
        status.HTTP_405_METHOD_NOT_ALLOWED,
        status.HTTP_429_TOO_MANY_REQUESTS,
    ]:
        api_exc = _coerce_to_api_exception(exc)
        if api_exc is None:
            return response
        detail, code = _normalize_detail_and_code(api_exc, data)
        response.data = {"detail": detail, "code": code}

    elif status_code == status.HTTP_400_BAD_REQUEST:
        if isinstance(exc, ValidationError):
            response.data = _build_400_payload(exc, data)
        else:
            api_exc = _coerce_to_api_exception(exc)
            if api_exc is None:
                return response
            detail, code = _normalize_detail_and_code(api_exc, data)
            response.data = {"detail": detail, "code": code}

    return response
