"""
Dashboard analytics for non-soft-deleted `FinancialRecord` rows.

Uses the default model manager (``deleted_at IS NULL``). Aggregations run as a few
separate ORM queries (totals, by-category, recent slice, monthly buckets).

**HTTP query params** (parsed in ``parse_dashboard_query_params``):

- ``date_from`` / ``date_to`` — optional ``YYYY-MM-DD``; filter ``occurred_at`` by UTC
  calendar date, inclusive of both days (same as list filters).
- ``recent_limit`` — optional int, default 10, max 50.

**``build_dashboard_summary`` return keys** match the API: ``totals``, ``by_category``,
``recent_activity``, ``monthly_trend``.
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Any
from zoneinfo import ZoneInfo

from django.db.models import DecimalField, Q, Sum, Value
from django.db.models.functions import Coalesce, TruncMonth
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from finance.models import FinancialRecord

# Month bucketing and Coalesce/Sum output typing for ORM aggregates.
UTC = ZoneInfo("UTC")
_AMOUNT_FIELD = DecimalField(max_digits=14, decimal_places=2)
_ZERO_DECIMAL = Value(Decimal("0"))


def parse_dashboard_query_params(
    query_params,
) -> tuple[date | None, date | None, int]:
    """
    Read dashboard query string (e.g. ``request.query_params``).

    Returns ``(date_from, date_to, recent_limit)``. Omitted date params are ``None``.
    Raises DRF ``ValidationError`` when ``date_from`` / ``date_to`` are present but
    not valid ISO dates (``YYYY-MM-DD``).
    """
    fields: dict[str, list[str]] = {}
    df_raw = query_params.get("date_from")
    dt_raw = query_params.get("date_to")
    date_from = None
    date_to = None
    if df_raw not in (None, ""):
        try:
            date_from = date.fromisoformat(str(df_raw))
        except ValueError:
            fields["date_from"] = ["Enter a valid date (YYYY-MM-DD)."]
    if dt_raw not in (None, ""):
        try:
            date_to = date.fromisoformat(str(dt_raw))
        except ValueError:
            fields["date_to"] = ["Enter a valid date (YYYY-MM-DD)."]
    if fields:
        raise ValidationError(fields)

    recent_limit = _parse_recent_limit(query_params.get("recent_limit"))
    return date_from, date_to, recent_limit


def _parse_recent_limit(raw: str | None) -> int:
    """Clamp to ``[1, 50]``; missing or non-integer values use default ``10``."""
    default, cap = 10, 50
    if raw is None or raw == "":
        return default
    try:
        n = int(raw)
    except (TypeError, ValueError):
        return default
    return max(1, min(cap, n))


def _month_start(d: date) -> date:
    """First calendar day of the month containing ``d``."""
    return date(d.year, d.month, 1)


def _add_months(first_of_month: date, delta: int) -> date:
    """Move from a month start by ``delta`` months (``delta`` may be negative)."""
    m = first_of_month.month - 1 + delta
    y = first_of_month.year + m // 12
    m = m % 12 + 1
    return date(y, m, 1)


def _trend_month_bounds(
    date_from: date | None,
    date_to: date | None,
    *,
    today_utc: date,
) -> tuple[date, date]:
    """
    Inclusive UTC month range for ``monthly_trend`` (first of month → first of month).

    Rules: both dates set → months spanned by those calendar dates;
    only ``date_from`` → through current month; only ``date_to`` → six months ending
    that month; neither → last six months including the current month.
    """
    cur = _month_start(today_utc)
    if date_from is not None and date_to is not None:
        start = _month_start(date_from)
        end = _month_start(date_to)
        if start > end:
            start, end = end, start
        return start, end
    if date_from is not None:
        return _month_start(date_from), cur
    if date_to is not None:
        end = _month_start(date_to)
        return _add_months(end, -5), end
    return _add_months(cur, -5), cur


def _apply_occurred_date_filter(qs, date_from: date | None, date_to: date | None):
    """Restrict queryset to ``occurred_at`` calendar dates (inclusive) in the DB/TZ sense."""
    if date_from is not None:
        qs = qs.filter(occurred_at__date__gte=date_from)
    if date_to is not None:
        qs = qs.filter(occurred_at__date__lte=date_to)
    return qs


def _money_str(value: Decimal) -> str:
    """API amounts as two-decimal strings (e.g. ``12.30``)."""
    return f"{value.quantize(Decimal('0.01')):.2f}"


def _occurred_at_iso_z(dt) -> str:
    """Serialize datetimes as UTC ISO-8601 with a ``Z`` suffix."""
    if timezone.is_naive(dt):
        dt = timezone.make_aware(dt, UTC)
    else:
        dt = dt.astimezone(UTC)
    return dt.isoformat().replace("+00:00", "Z")


def build_dashboard_summary(
    *,
    date_from: date | None = None,
    date_to: date | None = None,
    recent_limit: int = 10,
    today_utc: date | None = None,
) -> dict[str, Any]:
    """
    Compute dashboard payload from the same filtered slice of active records.

    ``date_from`` / ``date_to`` narrow **all** sections (totals, categories, recent,
    trend data). ``monthly_trend`` still emits every month in the trend window; months
    with no rows show zero sums.

    ``today_utc`` is only for tests or callers that need a fixed “current” day; default
    is derived from ``timezone.now()`` in UTC.
    """
    if today_utc is None:
        now = timezone.now()
        if timezone.is_naive(now):
            now = timezone.make_aware(now, UTC)
        today_utc = now.astimezone(UTC).date()

    base = FinancialRecord.objects.all()
    qs = _apply_occurred_date_filter(base, date_from, date_to)

    agg = qs.aggregate(
        income=Coalesce(
            Sum(
                "amount",
                filter=Q(type=FinancialRecord.EntryType.INCOME),
            ),
            _ZERO_DECIMAL,
            output_field=_AMOUNT_FIELD,
        ),
        expense=Coalesce(
            Sum(
                "amount",
                filter=Q(type=FinancialRecord.EntryType.EXPENSE),
            ),
            _ZERO_DECIMAL,
            output_field=_AMOUNT_FIELD,
        ),
    )
    income = agg["income"] or Decimal("0")
    expense = agg["expense"] or Decimal("0")
    net = income - expense

    totals = {
        "income": _money_str(income),
        "expense": _money_str(expense),
        "net": _money_str(net),
    }

    by_cat_rows = (
        qs.values("category", "type")
        .annotate(total=Sum("amount"))
        .order_by("category", "type")
    )
    by_category = [
        {
            "category": row["category"],
            "type": row["type"],
            "total": _money_str(row["total"] or Decimal("0")),
        }
        for row in by_cat_rows
    ]

    recent_qs = qs.order_by("-occurred_at", "-id")[:recent_limit]
    recent_activity = []
    for rec in recent_qs:
        recent_activity.append(
            {
                "id": rec.pk,
                "amount": _money_str(rec.amount),
                "type": rec.type,
                "category": rec.category,
                "occurred_at": _occurred_at_iso_z(rec.occurred_at),
                "notes": rec.notes if rec.notes else None,
            }
        )

    trend_start, trend_end = _trend_month_bounds(
        date_from, date_to, today_utc=today_utc
    )
    monthly_trend = _monthly_trend_rows(qs, trend_start, trend_end)

    return {
        "totals": totals,
        "by_category": by_category,
        "recent_activity": recent_activity,
        "monthly_trend": monthly_trend,
    }


def _monthly_trend_rows(qs, trend_start: date, trend_end: date) -> list[dict]:
    """
    One grouped ORM query by UTC month, then fill gaps so every month from
    ``trend_start`` through ``trend_end`` appears with ``income`` / ``expense`` / ``net``.
    """
    income_sum = Coalesce(
        Sum("amount", filter=Q(type=FinancialRecord.EntryType.INCOME)),
        _ZERO_DECIMAL,
        output_field=_AMOUNT_FIELD,
    )
    expense_sum = Coalesce(
        Sum("amount", filter=Q(type=FinancialRecord.EntryType.EXPENSE)),
        _ZERO_DECIMAL,
        output_field=_AMOUNT_FIELD,
    )

    aggregated = (
        qs.annotate(period=TruncMonth("occurred_at", tzinfo=UTC))
        .values("period")
        .annotate(income=income_sum, expense=expense_sum)
        .order_by("period")
    )

    by_key: dict[tuple[int, int], tuple[Decimal, Decimal]] = {}
    for row in aggregated:
        p = row["period"]
        if p is None:
            continue
        if timezone.is_naive(p):
            p = timezone.make_aware(p, UTC)
        else:
            p = p.astimezone(UTC)
        key = (p.year, p.month)
        inc = row["income"] or Decimal("0")
        exp = row["expense"] or Decimal("0")
        by_key[key] = (inc, exp)

    out: list[dict] = []
    walk = trend_start
    while walk <= trend_end:
        key = (walk.year, walk.month)
        inc, exp = by_key.get(key, (Decimal("0"), Decimal("0")))
        period_start = datetime(walk.year, walk.month, 1, 0, 0, 0, tzinfo=UTC)
        period_iso = period_start.isoformat().replace("+00:00", "Z")
        out.append(
            {
                "period_start": period_iso,
                "income": _money_str(inc),
                "expense": _money_str(exp),
                "net": _money_str(inc - exp),
            }
        )
        walk = _add_months(walk, 1)

    return out
