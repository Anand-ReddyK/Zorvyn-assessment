from rest_framework.exceptions import AuthenticationFailed
from rest_framework_simplejwt.authentication import JWTAuthentication

from accounts.models import User


class ActiveUserJWTAuthentication(JWTAuthentication):
    """JWT auth that returns 401 for users with status != active."""

    def get_user(self, validated_token):
        user = super().get_user(validated_token)
        if user.status != User.Status.ACTIVE:
            raise AuthenticationFailed(
                {"detail": "User is inactive.", "code": "user_inactive"},
                code="user_inactive",
            )
        return user
