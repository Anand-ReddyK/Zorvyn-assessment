"""Unit tests for `config.exceptions` helpers (no HTTP to finance routes)."""

from django.test import TestCase
from rest_framework.exceptions import NotFound, ValidationError

from config import exceptions as exc_mod


class ExceptionHelpersTests(TestCase):
    def test_flatten_validation_errors_nested_dict(self):
        data = {"items": {"0": {"price": ["Must be positive."]}}}
        flat = exc_mod._flatten_validation_errors(data)
        self.assertIn("items.0.price", flat)
        self.assertEqual(flat["items.0.price"], ["Must be positive."])

    def test_build_400_payload_field_errors(self):
        exc = ValidationError()
        data = {"email": ["Invalid email."]}
        payload = exc_mod._build_400_payload(exc, data)
        self.assertEqual(payload["code"], "validation_error")
        self.assertIn("fields", payload)
        self.assertEqual(payload["fields"]["email"], ["Invalid email."])

    def test_normalize_detail_and_code_simple_dict(self):
        exc = NotFound()
        detail, code = exc_mod._normalize_detail_and_code(exc, {"detail": "Missing."})
        self.assertEqual(detail, "Missing.")
        self.assertEqual(code, "not_found")
