"""Dashboard summary aggregation (Phase 7 — DESIGN §5)."""

from datetime import date, datetime
from decimal import Decimal
from zoneinfo import ZoneInfo

from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from accounts.models import User
from finance.models import FinancialRecord
from finance.services import build_dashboard_summary

UTC = ZoneInfo("UTC")


def _bearer(user):
    return f"Bearer {RefreshToken.for_user(user).access_token}"


class DashboardSummaryServiceTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user(
            email="dash_admin@example.com",
            password="testpass12345",
            name="Dash Admin",
            role=User.Role.ADMIN,
            status=User.Status.ACTIVE,
            is_staff=True,
        )

    def test_totals_by_category_recent_and_monthly_trend(self):
        FinancialRecord.objects.create(
            amount=Decimal("100.00"),
            type=FinancialRecord.EntryType.INCOME,
            category="salary",
            occurred_at=datetime(2026, 1, 15, 10, 0, 0, tzinfo=UTC),
            notes="",
            created_by=self.admin,
        )
        FinancialRecord.objects.create(
            amount=Decimal("40.00"),
            type=FinancialRecord.EntryType.EXPENSE,
            category="travel",
            occurred_at=datetime(2026, 1, 16, 10, 0, 0, tzinfo=UTC),
            created_by=self.admin,
        )
        FinancialRecord.objects.create(
            amount=Decimal("50.00"),
            type=FinancialRecord.EntryType.INCOME,
            category="bonus",
            occurred_at=datetime(2026, 3, 10, 12, 0, 0, tzinfo=UTC),
            created_by=self.admin,
        )
        FinancialRecord.objects.create(
            amount=Decimal("20.00"),
            type=FinancialRecord.EntryType.EXPENSE,
            category="meals",
            occurred_at=datetime(2026, 4, 2, 9, 0, 0, tzinfo=UTC),
            notes="lunch",
            created_by=self.admin,
        )

        out = build_dashboard_summary(
            today_utc=date(2026, 4, 15),
            recent_limit=2,
        )

        self.assertEqual(
            out["totals"],
            {"income": "150.00", "expense": "60.00", "net": "90.00"},
        )

        self.assertEqual(
            [x["category"] for x in out["by_category"]],
            ["bonus", "meals", "salary", "travel"],
        )

        self.assertEqual(len(out["recent_activity"]), 2)
        self.assertEqual(out["recent_activity"][0]["category"], "meals")
        self.assertEqual(out["recent_activity"][0]["notes"], "lunch")
        self.assertEqual(out["recent_activity"][1]["category"], "bonus")

        # Default trend: 6 UTC months ending April 2026 → Nov 2025 … Apr 2026
        self.assertEqual(len(out["monthly_trend"]), 6)
        self.assertEqual(out["monthly_trend"][0]["period_start"], "2025-11-01T00:00:00Z")
        self.assertEqual(out["monthly_trend"][-1]["period_start"], "2026-04-01T00:00:00Z")
        jan = next(
            m
            for m in out["monthly_trend"]
            if m["period_start"] == "2026-01-01T00:00:00Z"
        )
        self.assertEqual(jan["income"], "100.00")
        self.assertEqual(jan["expense"], "40.00")
        self.assertEqual(jan["net"], "60.00")

    def test_soft_deleted_excluded(self):
        a = FinancialRecord.objects.create(
            amount=Decimal("10.00"),
            type=FinancialRecord.EntryType.INCOME,
            category="a",
            occurred_at=datetime(2026, 2, 1, 0, 0, 0, tzinfo=UTC),
            created_by=self.admin,
        )
        FinancialRecord.objects.create(
            amount=Decimal("5.00"),
            type=FinancialRecord.EntryType.INCOME,
            category="b",
            occurred_at=datetime(2026, 2, 2, 0, 0, 0, tzinfo=UTC),
            created_by=self.admin,
        )
        a.deleted_at = datetime(2026, 2, 3, 0, 0, 0, tzinfo=UTC)
        a.save(update_fields=["deleted_at", "updated_at"])

        out = build_dashboard_summary(today_utc=date(2026, 2, 15))
        self.assertEqual(out["totals"]["income"], "5.00")
        self.assertEqual(len(out["by_category"]), 1)

    def test_date_from_date_to_filter(self):
        FinancialRecord.objects.create(
            amount=Decimal("1.00"),
            type=FinancialRecord.EntryType.INCOME,
            category="x",
            occurred_at=datetime(2026, 1, 31, 23, 0, 0, tzinfo=UTC),
            created_by=self.admin,
        )
        FinancialRecord.objects.create(
            amount=Decimal("2.00"),
            type=FinancialRecord.EntryType.INCOME,
            category="y",
            occurred_at=datetime(2026, 2, 15, 12, 0, 0, tzinfo=UTC),
            created_by=self.admin,
        )
        out = build_dashboard_summary(
            date_from=date(2026, 2, 1),
            date_to=date(2026, 2, 28),
            today_utc=date(2026, 6, 1),
        )
        self.assertEqual(out["totals"]["income"], "2.00")
        # Trend bounds: Feb 2026 only when both dates in February
        self.assertEqual(len(out["monthly_trend"]), 1)
        self.assertEqual(
            out["monthly_trend"][0]["period_start"],
            "2026-02-01T00:00:00Z",
        )


class DashboardSummaryApiTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.viewer = User.objects.create_user(
            email="dash_viewer@example.com",
            password="testpass12345",
            name="Dash Viewer",
            role=User.Role.VIEWER,
            status=User.Status.ACTIVE,
        )

    def test_invalid_date_from_returns_400_contract(self):
        r = self.client.get(
            "/api/dashboard/summary/",
            {"date_from": "not-a-date"},
            HTTP_AUTHORIZATION=_bearer(self.viewer),
        )
        self.assertEqual(r.status_code, 400)
        b = r.json()
        self.assertEqual(b["code"], "validation_error")
        self.assertIn("date_from", b["fields"])
