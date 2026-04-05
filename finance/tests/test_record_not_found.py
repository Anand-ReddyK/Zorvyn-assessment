"""404 response shape for financial record detail (project exception handler)."""

from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from accounts.models import User


class RecordDetailNotFoundTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.analyst = User.objects.create_user(
            email="nf_analyst@example.com",
            password="testpass12345",
            name="NF Analyst",
            role=User.Role.ANALYST,
            status=User.Status.ACTIVE,
        )
        token = str(RefreshToken.for_user(self.analyst).access_token)
        self.auth = {"HTTP_AUTHORIZATION": f"Bearer {token}"}

    def test_record_detail_404_unified_shape(self):
        r = self.client.get("/api/records/999999/", **self.auth)
        self.assertEqual(r.status_code, 404)
        b = r.json()
        self.assertEqual(set(b.keys()), {"detail", "code"})
        self.assertEqual(b["code"], "not_found")
