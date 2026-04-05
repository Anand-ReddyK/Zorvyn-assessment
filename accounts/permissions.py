from rest_framework import permissions

from accounts.models import User


class IsAdmin(permissions.BasePermission):
    """Role admin only"""

    def has_permission(self, request, view):
        return (
            request.user
            and request.user.is_authenticated
            and getattr(request.user, "role", None) == User.Role.ADMIN
        )


class IsAnalystOrAdmin(permissions.BasePermission):
    """Analyst or admin — can read financial records"""

    def has_permission(self, request, view):
        role = getattr(request.user, "role", None)
        return request.user and request.user.is_authenticated and role in (
            User.Role.ANALYST,
            User.Role.ADMIN,
        )


class CanAccessDashboard(permissions.BasePermission):
    """Viewer, analyst, or admin — dashboard summary"""

    def has_permission(self, request, view):
        role = getattr(request.user, "role", None)
        return request.user and request.user.is_authenticated and role in (
            User.Role.VIEWER,
            User.Role.ANALYST,
            User.Role.ADMIN,
        )
