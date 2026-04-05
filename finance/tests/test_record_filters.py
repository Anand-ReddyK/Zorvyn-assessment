"""List filtering for `/api/records/` (Phase 6 — django-filter)."""

from datetime import datetime
from decimal import Decimal
from zoneinfo import ZoneInfo

from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from accounts.models import User
from finance.models import FinancialRecord


def _bearer(user):
    return f"Bearer {RefreshToken.for_user(user).access_token}"


class RecordListFilterTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.admin = User.objects.create_user(
            email="filter_admin@example.com",
            password="testpass12345",
            name="Filter Admin",
            role=User.Role.ADMIN,
            status=User.Status.ACTIVE,
            is_staff=True,
        )
        self.analyst = User.objects.create_user(
            email="filter_analyst@example.com",
            password="testpass12345",
            name="Filter Analyst",
            role=User.Role.ANALYST,
            status=User.Status.ACTIVE,
        )
        utc = ZoneInfo("UTC")
        self.r_early = FinancialRecord.objects.create(
            amount=Decimal("1.00"),
            type=FinancialRecord.EntryType.INCOME,
            category="salary",
            occurred_at=datetime(2026, 1, 10, 12, 0, tzinfo=utc),
            created_by=self.admin,
        )
        self.r_mid = FinancialRecord.objects.create(
            amount=Decimal("2.00"),
            type=FinancialRecord.EntryType.EXPENSE,
            category="travel",
            occurred_at=datetime(2026, 3, 15, 8, 30, tzinfo=utc),
            created_by=self.admin,
        )
        self.r_late = FinancialRecord.objects.create(
            amount=Decimal("3.00"),
            type=FinancialRecord.EntryType.INCOME,
            category="salary",
            occurred_at=datetime(2026, 5, 1, 0, 0, tzinfo=utc),
            created_by=self.admin,
        )

    def _ids(self, response):
        self.assertEqual(response.status_code, 200)
        data = response.json()
        return {row["id"] for row in data["results"]}

    def test_filter_type(self):
        r = self.client.get(
            "/api/records/",
            {"type": "expense"},
            HTTP_AUTHORIZATION=_bearer(self.analyst),
        )
        self.assertEqual(self._ids(r), {self.r_mid.pk})

    def test_filter_category(self):
        r = self.client.get(
            "/api/records/",
            {"category": "salary"},
            HTTP_AUTHORIZATION=_bearer(self.analyst),
        )
        self.assertEqual(self._ids(r), {self.r_early.pk, self.r_late.pk})

    def test_filter_date_from_and_date_to_inclusive(self):
        r = self.client.get(
            "/api/records/",
            {"date_from": "2026-03-15", "date_to": "2026-03-15"},
            HTTP_AUTHORIZATION=_bearer(self.analyst),
        )
        self.assertEqual(self._ids(r), {self.r_mid.pk})

    def test_filter_date_range(self):
        r = self.client.get(
            "/api/records/",
            {"date_from": "2026-01-01", "date_to": "2026-04-01"},
            HTTP_AUTHORIZATION=_bearer(self.analyst),
        )
        self.assertEqual(self._ids(r), {self.r_early.pk, self.r_mid.pk})
