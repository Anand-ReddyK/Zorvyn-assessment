"""Unit tests for `accounts.permissions` (no HTTP)."""

from django.contrib.auth.models import AnonymousUser
from django.test import RequestFactory, TestCase

from accounts.models import User
from accounts.permissions import CanAccessDashboard, IsAdmin, IsAnalystOrAdmin


class PermissionClassTests(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.dummy_view = object()

    def _request(self, user):
        request = self.factory.get("/fake/")
        request.user = user
        return request

    def test_is_admin_true_only_for_admin_role(self):
        permission = IsAdmin()
        admin = User(
            email="a@e.com",
            name="A",
            role=User.Role.ADMIN,
            status=User.Status.ACTIVE,
        )
        analyst = User(
            email="an@e.com",
            name="An",
            role=User.Role.ANALYST,
            status=User.Status.ACTIVE,
        )
        self.assertTrue(permission.has_permission(self._request(admin), self.dummy_view))
        self.assertFalse(permission.has_permission(self._request(analyst), self.dummy_view))
        self.assertFalse(permission.has_permission(self._request(AnonymousUser()), self.dummy_view))

    def test_is_analyst_or_admin_excludes_viewer(self):
        permission = IsAnalystOrAdmin()
        viewer = User(
            email="v@e.com",
            name="V",
            role=User.Role.VIEWER,
            status=User.Status.ACTIVE,
        )
        analyst = User(
            email="an@e.com",
            name="An",
            role=User.Role.ANALYST,
            status=User.Status.ACTIVE,
        )
        admin = User(
            email="ad@e.com",
            name="Ad",
            role=User.Role.ADMIN,
            status=User.Status.ACTIVE,
        )
        self.assertFalse(permission.has_permission(self._request(viewer), self.dummy_view))
        self.assertTrue(permission.has_permission(self._request(analyst), self.dummy_view))
        self.assertTrue(permission.has_permission(self._request(admin), self.dummy_view))

    def test_can_access_dashboard_all_three_roles(self):
        permission = CanAccessDashboard()
        for role in (User.Role.VIEWER, User.Role.ANALYST, User.Role.ADMIN):
            user = User(email=f"{role}@e.com", name=role, role=role, status=User.Status.ACTIVE)
            self.assertTrue(permission.has_permission(self._request(user), self.dummy_view))
        self.assertFalse(permission.has_permission(self._request(AnonymousUser()), self.dummy_view))
