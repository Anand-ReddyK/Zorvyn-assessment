"""Rate limiting (DRF throttles) on JWT and default API traffic."""

from django.core.cache import cache
from django.test import TestCase
from rest_framework.settings import api_settings
from rest_framework.test import APIClient
from rest_framework.throttling import ScopedRateThrottle


class JwtObtainThrottleTests(TestCase):
    def test_third_login_attempt_in_window_returns_429_shape(self):
        # DRF binds SimpleRateThrottle.THROTTLE_RATES at import time; patch the class
        # for this test instead of override_settings (which does not replace that ref).
        orig_rates = ScopedRateThrottle.THROTTLE_RATES
        ScopedRateThrottle.THROTTLE_RATES = {
            **dict(api_settings.DEFAULT_THROTTLE_RATES),
            "jwt_obtain": "2/minute",
        }
        try:
            cache.clear()
            client = APIClient()
            url = "/api/auth/token/"
            body = {"email": "nobody@example.com", "password": "wrong"}
            for _ in range(2):
                r = client.post(url, body, format="json")
                self.assertNotEqual(r.status_code, 429, r.content)
            r3 = client.post(url, body, format="json")
            self.assertEqual(r3.status_code, 429, r3.content)
            data = r3.json()
            self.assertEqual(set(data.keys()), {"detail", "code"})
            self.assertEqual(data["code"], "throttled")
        finally:
            ScopedRateThrottle.THROTTLE_RATES = orig_rates
