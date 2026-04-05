"""Unit tests for ``finance.services`` helpers (no HTTP)."""

from datetime import date, datetime
from decimal import Decimal
from zoneinfo import ZoneInfo

from django.test import SimpleTestCase, TestCase
from rest_framework.exceptions import ValidationError

from accounts.models import User
from finance.models import FinancialRecord
from finance.services import (
    _add_months,
    _apply_occurred_date_filter,
    _money_str,
    _month_start,
    _occurred_at_iso_z,
    _trend_month_bounds,
    parse_dashboard_query_params,
)

UTC = ZoneInfo("UTC")


class ParseDashboardQueryParamsTests(SimpleTestCase):
    def test_empty_returns_defaults(self):
        self.assertEqual(
            parse_dashboard_query_params({}),
            (None, None, 10),
        )

    def test_dates_and_recent_limit(self):
        qp = {
            "date_from": "2026-03-01",
            "date_to": "2026-03-31",
            "recent_limit": "5",
        }
        self.assertEqual(
            parse_dashboard_query_params(qp),
            (date(2026, 3, 1), date(2026, 3, 31), 5),
        )

    def test_omitted_dates_are_none(self):
        self.assertEqual(
            parse_dashboard_query_params({"recent_limit": "1"}),
            (None, None, 1),
        )

    def test_recent_limit_clamped_and_invalid_falls_back(self):
        self.assertEqual(parse_dashboard_query_params({"recent_limit": "0"})[2], 1)
        self.assertEqual(parse_dashboard_query_params({"recent_limit": "99"})[2], 50)
        self.assertEqual(parse_dashboard_query_params({"recent_limit": "nope"})[2], 10)

    def test_invalid_date_from_raises(self):
        with self.assertRaises(ValidationError) as ctx:
            parse_dashboard_query_params({"date_from": "bad"})
        self.assertIn("date_from", ctx.exception.detail)

    def test_invalid_date_to_raises(self):
        with self.assertRaises(ValidationError) as ctx:
            parse_dashboard_query_params({"date_to": "2026-13-01"})
        self.assertIn("date_to", ctx.exception.detail)


class TrendMonthBoundsTests(SimpleTestCase):
    def test_default_six_months_including_current(self):
        start, end = _trend_month_bounds(None, None, today_utc=date(2026, 4, 15))
        self.assertEqual(start, date(2025, 11, 1))
        self.assertEqual(end, date(2026, 4, 1))

    def test_date_from_only_through_current_month(self):
        start, end = _trend_month_bounds(
            date(2026, 1, 20), None, today_utc=date(2026, 4, 15)
        )
        self.assertEqual(start, date(2026, 1, 1))
        self.assertEqual(end, date(2026, 4, 1))

    def test_date_to_only_six_months_ending_that_month(self):
        start, end = _trend_month_bounds(
            None, date(2026, 3, 10), today_utc=date(2026, 6, 1)
        )
        self.assertEqual(end, date(2026, 3, 1))
        self.assertEqual(start, date(2025, 10, 1))

    def test_both_dates_swapped_normalized(self):
        start, end = _trend_month_bounds(
            date(2026, 5, 1), date(2026, 2, 1), today_utc=date(2026, 6, 1)
        )
        self.assertEqual(start, date(2026, 2, 1))
        self.assertEqual(end, date(2026, 5, 1))


class MonthMathTests(SimpleTestCase):
    def test_month_start(self):
        self.assertEqual(_month_start(date(2026, 7, 31)), date(2026, 7, 1))

    def test_add_months_across_year(self):
        self.assertEqual(
            _add_months(date(2025, 12, 1), 1),
            date(2026, 1, 1),
        )
        self.assertEqual(
            _add_months(date(2026, 1, 1), -1),
            date(2025, 12, 1),
        )


class FormatHelpersTests(SimpleTestCase):
    def test_money_str(self):
        self.assertEqual(_money_str(Decimal("12.3")), "12.30")
        self.assertEqual(_money_str(Decimal("0")), "0.00")

    def test_occurred_at_iso_z(self):
        dt = datetime(2026, 1, 2, 15, 30, 0, tzinfo=UTC)
        self.assertEqual(_occurred_at_iso_z(dt), "2026-01-02T15:30:00Z")


class ApplyOccurredDateFilterTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user(
            email="svc_filt@example.com",
            password="testpass12345",
            name="Svc Filt",
            role=User.Role.ADMIN,
            status=User.Status.ACTIVE,
            is_staff=True,
        )

    def test_filter_inclusive_calendar_days(self):
        FinancialRecord.objects.create(
            amount=Decimal("1.00"),
            type=FinancialRecord.EntryType.INCOME,
            category="a",
            occurred_at=datetime(2026, 2, 28, 23, 0, 0, tzinfo=UTC),
            created_by=self.admin,
        )
        FinancialRecord.objects.create(
            amount=Decimal("2.00"),
            type=FinancialRecord.EntryType.INCOME,
            category="b",
            occurred_at=datetime(2026, 3, 1, 1, 0, 0, tzinfo=UTC),
            created_by=self.admin,
        )
        qs = FinancialRecord.objects.all()
        feb = _apply_occurred_date_filter(qs, date(2026, 2, 1), date(2026, 2, 28))
        self.assertEqual(feb.count(), 1)
        both = _apply_occurred_date_filter(qs, date(2026, 2, 1), date(2026, 3, 1))
        self.assertEqual(both.count(), 2)
