"""
User API serializer.

API **400** responses are shaped by `config.exceptions.custom_exception_handler`:
`{"detail", "code", "fields": {...}}` for field errors (`code` is `validation_error`).
"""

from django.core.exceptions import ValidationError as DjangoValidationError
from django.contrib.auth.password_validation import (
    validate_password as run_password_validators,
)
from rest_framework import serializers

from accounts.models import User


class UserSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, required=False, min_length=8)

    class Meta:
        model = User
        fields = (
            "id",
            "email",
            "name",
            "password",
            "role",
            "status",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("id", "created_at", "updated_at")

    def validate_name(self, value):
        if not (value and str(value).strip()):
            raise serializers.ValidationError(["This field may not be blank."])
        return value.strip()

    def validate(self, attrs):
        password = attrs.get("password")
        if not password:
            return attrs
        user = self.instance
        try:
            run_password_validators(password, user=user)
        except DjangoValidationError as exc:
            raise serializers.ValidationError(
                {"password": list(exc.messages)}
            ) from exc
        return attrs

    def create(self, validated_data):
        password = validated_data.pop("password", None)
        if not password:
            raise serializers.ValidationError(
                {"password": ["This field is required."]}
            )
        user = User(**validated_data)
        user.set_password(password)
        user.save()
        return user

    def update(self, instance, validated_data):
        password = validated_data.pop("password", None)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        if password:
            instance.set_password(password)
        instance.save()
        return instance
