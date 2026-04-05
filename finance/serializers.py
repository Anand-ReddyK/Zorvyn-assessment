from decimal import Decimal

from rest_framework import serializers

from finance.models import FinancialRecord


class FinancialRecordSerializer(serializers.ModelSerializer):
    class Meta:
        model = FinancialRecord
        fields = (
            "id",
            "amount",
            "type",
            "category",
            "occurred_at",
            "notes",
            "created_by",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("id", "created_by", "created_at", "updated_at")

    def validate_amount(self, value: Decimal) -> Decimal:
        if value < 0:
            raise serializers.ValidationError("Amount must be zero or greater.")
        return value
