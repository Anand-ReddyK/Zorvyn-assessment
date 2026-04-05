"""Soft delete vs permanent (hard) delete on `/api/records/`."""

from decimal import Decimal

from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from accounts.models import User
from finance.models import FinancialRecord


def _bearer(user):
    return f"Bearer {RefreshToken.for_user(user).access_token}"


class RecordDeleteTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.admin = User.objects.create_user(
            email="del_admin@example.com",
            password="testpass12345",
            name="Del Admin",
            role=User.Role.ADMIN,
            status=User.Status.ACTIVE,
            is_staff=True,
        )
        self.analyst = User.objects.create_user(
            email="del_analyst@example.com",
            password="testpass12345",
            name="Del Analyst",
            role=User.Role.ANALYST,
            status=User.Status.ACTIVE,
        )

    def test_admin_soft_delete_sets_deleted_at(self):
        rec = FinancialRecord.objects.create(
            amount=Decimal("5.00"),
            type=FinancialRecord.EntryType.INCOME,
            category="soft",
            occurred_at=timezone.now(),
            created_by=self.admin,
        )
        r = self.client.delete(
            f"/api/records/{rec.pk}/",
            HTTP_AUTHORIZATION=_bearer(self.admin),
        )
        self.assertEqual(r.status_code, 204)
        rec.refresh_from_db()
        self.assertIsNotNone(rec.deleted_at)

    def test_admin_permanent_delete_active_row(self):
        rec = FinancialRecord.objects.create(
            amount=Decimal("6.00"),
            type=FinancialRecord.EntryType.EXPENSE,
            category="hard_active",
            occurred_at=timezone.now(),
            created_by=self.admin,
        )
        pk = rec.pk
        r = self.client.delete(
            f"/api/records/{pk}/permanent/",
            HTTP_AUTHORIZATION=_bearer(self.admin),
        )
        self.assertEqual(r.status_code, 204)
        self.assertFalse(FinancialRecord.all_objects.filter(pk=pk).exists())

    def test_admin_permanent_delete_soft_deleted_row(self):
        rec = FinancialRecord.objects.create(
            amount=Decimal("7.00"),
            type=FinancialRecord.EntryType.EXPENSE,
            category="hard_soft",
            occurred_at=timezone.now(),
            created_by=self.admin,
        )
        rec.deleted_at = timezone.now()
        rec.save(update_fields=["deleted_at", "updated_at"])
        pk = rec.pk
        r = self.client.delete(
            f"/api/records/{pk}/permanent/",
            HTTP_AUTHORIZATION=_bearer(self.admin),
        )
        self.assertEqual(r.status_code, 204)
        self.assertFalse(FinancialRecord.all_objects.filter(pk=pk).exists())

    def test_analyst_cannot_soft_delete_403(self):
        rec = FinancialRecord.objects.create(
            amount=Decimal("8.00"),
            type=FinancialRecord.EntryType.INCOME,
            category="no",
            occurred_at=timezone.now(),
            created_by=self.admin,
        )
        r = self.client.delete(
            f"/api/records/{rec.pk}/",
            HTTP_AUTHORIZATION=_bearer(self.analyst),
        )
        self.assertEqual(r.status_code, 403)
        self.assertEqual(r.json()["code"], "permission_denied")

    def test_analyst_cannot_permanent_delete_403(self):
        rec = FinancialRecord.objects.create(
            amount=Decimal("9.00"),
            type=FinancialRecord.EntryType.INCOME,
            category="no2",
            occurred_at=timezone.now(),
            created_by=self.admin,
        )
        r = self.client.delete(
            f"/api/records/{rec.pk}/permanent/",
            HTTP_AUTHORIZATION=_bearer(self.analyst),
        )
        self.assertEqual(r.status_code, 403)
        self.assertEqual(r.json()["code"], "permission_denied")
