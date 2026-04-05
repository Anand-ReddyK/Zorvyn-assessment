"""Role-based access tests for `/api/users/` (UserViewSet)."""

from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from accounts.models import User


def _bearer(user):
    return f"Bearer {RefreshToken.for_user(user).access_token}"


def _assert_403_permission_denied(testcase, response):
    testcase.assertEqual(response.status_code, 403)
    body = response.json()
    testcase.assertEqual(set(body.keys()), {"detail", "code"})
    testcase.assertEqual(body["code"], "permission_denied")


class UserApiRoleAccessTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.admin = User.objects.create_user(
            email="user_api_admin@example.com",
            password="testpass12345",
            name="User API Admin",
            role=User.Role.ADMIN,
            status=User.Status.ACTIVE,
            is_staff=True,
        )
        self.analyst = User.objects.create_user(
            email="user_api_analyst@example.com",
            password="testpass12345",
            name="User API Analyst",
            role=User.Role.ANALYST,
            status=User.Status.ACTIVE,
        )
        self.viewer = User.objects.create_user(
            email="user_api_viewer@example.com",
            password="testpass12345",
            name="User API Viewer",
            role=User.Role.VIEWER,
            status=User.Status.ACTIVE,
        )

    def test_admin_can_list_users(self):
        r = self.client.get("/api/users/", HTTP_AUTHORIZATION=_bearer(self.admin))
        self.assertEqual(r.status_code, 200)

    def test_viewer_and_analyst_cannot_list_users(self):
        for user in (self.viewer, self.analyst):
            with self.subTest(role=user.role):
                r = self.client.get("/api/users/", HTTP_AUTHORIZATION=_bearer(user))
                _assert_403_permission_denied(self, r)

    def test_viewer_and_analyst_cannot_create_user(self):
        payload = {
            "email": "new_user@example.com",
            "name": "New User",
            "password": "testpass12345",
            "role": User.Role.VIEWER,
            "status": User.Status.ACTIVE,
        }
        for user in (self.viewer, self.analyst):
            with self.subTest(role=user.role):
                r = self.client.post(
                    "/api/users/",
                    payload,
                    format="json",
                    HTTP_AUTHORIZATION=_bearer(user),
                )
                _assert_403_permission_denied(self, r)

    def test_viewer_and_analyst_cannot_retrieve_user(self):
        for user in (self.viewer, self.analyst):
            with self.subTest(role=user.role):
                r = self.client.get(
                    f"/api/users/{self.admin.pk}/",
                    HTTP_AUTHORIZATION=_bearer(user),
                )
                _assert_403_permission_denied(self, r)

    def test_viewer_and_analyst_cannot_update_user(self):
        for user in (self.viewer, self.analyst):
            with self.subTest(role=user.role):
                r = self.client.patch(
                    f"/api/users/{self.admin.pk}/",
                    {"name": "Should Not Apply"},
                    format="json",
                    HTTP_AUTHORIZATION=_bearer(user),
                )
                _assert_403_permission_denied(self, r)

    def test_viewer_and_analyst_cannot_delete_other_user(self):
        other = User.objects.create_user(
            email="other_target@example.com",
            password="testpass12345",
            name="Other Target",
            role=User.Role.VIEWER,
        )
        for user in (self.viewer, self.analyst):
            with self.subTest(role=user.role):
                r = self.client.delete(
                    f"/api/users/{other.pk}/",
                    HTTP_AUTHORIZATION=_bearer(user),
                )
                _assert_403_permission_denied(self, r)
        self.assertTrue(User.objects.filter(pk=other.pk).exists())

    def test_admin_cannot_delete_self_403(self):
        r = self.client.delete(
            f"/api/users/{self.admin.pk}/",
            HTTP_AUTHORIZATION=_bearer(self.admin),
        )
        self.assertEqual(r.status_code, 403)
        b = r.json()
        self.assertEqual(b["code"], "permission_denied")
        self.assertIn("own", b["detail"].lower())

    def test_admin_can_delete_other_user(self):
        other = User.objects.create_user(
            email="delete_me@example.com",
            password="testpass12345",
            name="Delete Me",
            role=User.Role.VIEWER,
        )
        r = self.client.delete(
            f"/api/users/{other.pk}/",
            HTTP_AUTHORIZATION=_bearer(self.admin),
        )
        self.assertEqual(r.status_code, 204)
        self.assertFalse(User.objects.filter(pk=other.pk).exists())
