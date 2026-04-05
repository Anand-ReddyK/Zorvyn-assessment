"""JWT views with scoped rate limits (tighter than generic anonymous traffic)."""

from rest_framework.throttling import ScopedRateThrottle
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView


class ThrottledTokenObtainPairView(TokenObtainPairView):
    """Login: bounded by ``jwt_obtain`` in ``REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"]``."""

    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "jwt_obtain"


class ThrottledTokenRefreshView(TokenRefreshView):
    """Refresh: bounded by ``jwt_refresh`` rate."""

    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "jwt_refresh"
