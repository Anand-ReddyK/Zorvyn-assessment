"""Role-based access tests for finance API: `/api/records/`, `/api/dashboard/summary/`."""

from decimal import Decimal

from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from accounts.models import User
from finance.models import FinancialRecord


def _bearer(user):
    return f"Bearer {RefreshToken.for_user(user).access_token}"


class FinanceApiRoleAccessTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.admin = User.objects.create_user(
            email="fin_admin@example.com",
            password="testpass12345",
            name="Fin Admin",
            role=User.Role.ADMIN,
            status=User.Status.ACTIVE,
            is_staff=True,
        )
        self.analyst = User.objects.create_user(
            email="fin_analyst@example.com",
            password="testpass12345",
            name="Fin Analyst",
            role=User.Role.ANALYST,
            status=User.Status.ACTIVE,
        )
        self.viewer = User.objects.create_user(
            email="fin_viewer@example.com",
            password="testpass12345",
            name="Fin Viewer",
            role=User.Role.VIEWER,
            status=User.Status.ACTIVE,
        )
        FinancialRecord.objects.create(
            amount=Decimal("1.00"),
            type=FinancialRecord.EntryType.INCOME,
            category="seed",
            occurred_at=timezone.now(),
            created_by=self.admin,
        )

    # --- FinancialRecordViewSet ---

    def test_viewer_cannot_list_records_403(self):
        r = self.client.get("/api/records/", HTTP_AUTHORIZATION=_bearer(self.viewer))
        self.assertEqual(r.status_code, 403)
        self.assertEqual(r.json()["code"], "permission_denied")

    def test_analyst_can_list_records(self):
        r = self.client.get("/api/records/", HTTP_AUTHORIZATION=_bearer(self.analyst))
        self.assertEqual(r.status_code, 200)

    def test_analyst_cannot_create_record_403(self):
        r = self.client.post(
            "/api/records/",
            {
                "amount": "10.00",
                "type": "income",
                "category": "test",
                "occurred_at": timezone.now().isoformat(),
            },
            format="json",
            HTTP_AUTHORIZATION=_bearer(self.analyst),
        )
        self.assertEqual(r.status_code, 403)
        self.assertEqual(r.json()["code"], "permission_denied")

    def test_admin_can_create_record(self):
        r = self.client.post(
            "/api/records/",
            {
                "amount": "25.50",
                "type": "expense",
                "category": "office",
                "occurred_at": timezone.now().isoformat(),
            },
            format="json",
            HTTP_AUTHORIZATION=_bearer(self.admin),
        )
        self.assertEqual(r.status_code, 201, r.content)
        self.assertEqual(r.json()["created_by"], self.admin.pk)

    # --- DashboardSummaryView ---

    def test_viewer_can_dashboard(self):
        r = self.client.get(
            "/api/dashboard/summary/",
            HTTP_AUTHORIZATION=_bearer(self.viewer),
        )
        self.assertEqual(r.status_code, 200)
        self.assertIn("totals", r.json())
