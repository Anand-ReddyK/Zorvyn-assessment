"""404 response shape for financial record detail (project exception handler)."""

from decimal import Decimal

from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from accounts.models import User
from finance.models import FinancialRecord


def _bearer(user):
    return f"Bearer {RefreshToken.for_user(user).access_token}"


class RecordDetailNotFoundTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.admin = User.objects.create_user(
            email="nf_admin@example.com",
            password="testpass12345",
            name="NF Admin",
            role=User.Role.ADMIN,
            status=User.Status.ACTIVE,
            is_staff=True,
        )
        self.analyst = User.objects.create_user(
            email="nf_analyst@example.com",
            password="testpass12345",
            name="NF Analyst",
            role=User.Role.ANALYST,
            status=User.Status.ACTIVE,
        )
        self.auth_analyst = {"HTTP_AUTHORIZATION": _bearer(self.analyst)}
        self.auth_admin = {"HTTP_AUTHORIZATION": _bearer(self.admin)}

    def test_record_detail_404_unified_shape(self):
        r = self.client.get("/api/records/999999/", **self.auth_analyst)
        self.assertEqual(r.status_code, 404)
        b = r.json()
        self.assertEqual(set(b.keys()), {"detail", "code"})
        self.assertEqual(b["code"], "not_found")

    def test_soft_deleted_record_detail_404(self):
        rec = FinancialRecord.objects.create(
            amount=Decimal("9.00"),
            type=FinancialRecord.EntryType.EXPENSE,
            category="gone",
            occurred_at=timezone.now(),
            created_by=self.admin,
        )
        rec.deleted_at = timezone.now()
        rec.save(update_fields=["deleted_at", "updated_at"])

        for method, path, kwargs in (
            ("get", f"/api/records/{rec.pk}/", {}),
            (
                "patch",
                f"/api/records/{rec.pk}/",
                {"data": {"notes": "nope"}, "format": "json"},
            ),
            ("delete", f"/api/records/{rec.pk}/", {}),
        ):
            with self.subTest(method=method):
                fn = getattr(self.client, method)
                auth = self.auth_analyst if method == "get" else self.auth_admin
                r = fn(path, **kwargs, **auth)
                self.assertEqual(r.status_code, 404, r.content)
                self.assertEqual(r.json()["code"], "not_found")
