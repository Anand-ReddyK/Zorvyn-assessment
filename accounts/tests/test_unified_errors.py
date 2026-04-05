from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from accounts.models import User


class UnifiedErrorResponseTests(TestCase):
    """API errors use {detail, code} and optional {fields} per config.exceptions."""

    def setUp(self):
        self.client = APIClient()
        self.admin = User.objects.create_user(
            email="admin@example.com",
            password="testpass12345",
            name="Admin",
            role=User.Role.ADMIN,
            status=User.Status.ACTIVE,
            is_staff=True,
        )
        token = str(RefreshToken.for_user(self.admin).access_token)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")

    def test_validation_error_has_detail_code_fields(self):
        # Missing required fields on user create -> 400 with field map.
        response = self.client.post(
            "/api/users/",
            {"email": "new@example.com"},
            format="json",
        )
        self.assertEqual(response.status_code, 400)
        body = response.json()
        self.assertIn("detail", body)
        self.assertIn("code", body)
        self.assertEqual(body["code"], "validation_error")
        self.assertIn("fields", body)
        self.assertIsInstance(body["fields"], dict)
        self.assertIn("name", body["fields"])
        self.assertTrue(body["fields"]["name"])
