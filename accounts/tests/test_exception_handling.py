from django.test import TestCase
from rest_framework.permissions import IsAdminUser, IsAuthenticated
from rest_framework.response import Response
from rest_framework.test import APIRequestFactory, force_authenticate
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken

from accounts.models import User


class _ProtectedView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response({"ok": True})


class _AdminOnlyView(APIView):
    permission_classes = [IsAuthenticated, IsAdminUser]

    def get(self, request):
        return Response({"ok": True})


class AuthErrorResponseShapeTests(TestCase):
    """401/403 bodies are always {"detail": str, "code": str} (see config.exceptions)."""

    def setUp(self):
        self.factory = APIRequestFactory()

    def _get(self, view_cls, path="/test/", **extra):
        request = self.factory.get(path, **extra)
        return view_cls.as_view()(request)

    def test_401_no_credentials_has_detail_and_code(self):
        # Anonymous request should 401 with {detail, code}; code is not_authenticated.
        response = self._get(_ProtectedView)
        self.assertEqual(response.status_code, 401)
        self.assertIsInstance(response.data, dict)
        self.assertEqual(set(response.data.keys()), {"detail", "code"})
        self.assertEqual(response.data["code"], "not_authenticated")
        self.assertIn("credentials", response.data["detail"].lower())
    
    def test_401_invalid_bearer_token_has_detail_and_code(self):
        # Bad JWT should 401 with token_not_valid and the same JSON shape.
        response = self._get(
            _ProtectedView,
            HTTP_AUTHORIZATION="Bearer not-a-real-jwt",
        )
        self.assertEqual(response.status_code, 401)
        self.assertEqual(set(response.data.keys()), {"detail", "code"})
        self.assertEqual(response.data["code"], "token_not_valid")
        self.assertTrue(response.data["detail"])

    def test_401_inactive_user_with_valid_jwt(self):
        # Valid token but status inactive: ActiveUserJWTAuthentication returns user_inactive.
        user = User.objects.create_user(
            email="inactive@example.com",
            password="testpass12345",
            name="Inactive User",
            role=User.Role.VIEWER,
            status=User.Status.INACTIVE,
        )
        # SimpleJWT logs a warning when minting a token for an inactive user (expected here).
        token = str(RefreshToken.for_user(user).access_token)
        response = self._get(
            _ProtectedView,
            HTTP_AUTHORIZATION=f"Bearer {token}",
        )
        self.assertEqual(response.status_code, 401)
        self.assertEqual(set(response.data.keys()), {"detail", "code"})
        self.assertEqual(response.data["code"], "user_inactive")
        self.assertIn("inactive", response.data["detail"].lower())

    def test_200_active_user_with_valid_jwt(self):
        # Happy path: active user + valid JWT reaches the view (200).
        user = User.objects.create_user(
            email="active@example.com",
            password="testpass12345",
            name="Active User",
            role=User.Role.VIEWER,
            status=User.Status.ACTIVE,
        )
        token = str(RefreshToken.for_user(user).access_token)
        response = self._get(
            _ProtectedView,
            HTTP_AUTHORIZATION=f"Bearer {token}",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, {"ok": True})

    def test_403_permission_denied_same_shape(self):
        # Non-staff user on IsAdminUser view: 403 with {detail, code permission_denied}.
        user = User.objects.create_user(
            email="viewer@example.com",
            password="testpass12345",
            name="Viewer",
            role=User.Role.VIEWER,
            status=User.Status.ACTIVE,
        )
        request = self.factory.get("/admin-only/")
        force_authenticate(request, user=user)
        response = _AdminOnlyView.as_view()(request)
        self.assertEqual(response.status_code, 403)
        self.assertEqual(set(response.data.keys()), {"detail", "code"})
        self.assertEqual(response.data["code"], "permission_denied")

    def test_200_staff_user_admin_only_view(self):
        # Staff user passes IsAdminUser and gets 200 from the same admin-only view.
        user = User.objects.create_user(
            email="staff@example.com",
            password="testpass12345",
            name="Staff Admin",
            role=User.Role.ADMIN,
            status=User.Status.ACTIVE,
            is_staff=True,
        )
        request = self.factory.get("/admin-only/")
        force_authenticate(request, user=user)
        response = _AdminOnlyView.as_view()(request)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, {"ok": True})
