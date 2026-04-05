from django.conf import settings
from django.db import models


class FinancialRecordQuerySet(models.QuerySet):
    """QuerySet that can include soft-deleted rows when needed."""

    # exclude soft-deleted rows
    def active_only(self):
        return self.filter(deleted_at__isnull=True)


class FinancialRecordManager(models.Manager):
    """Default manager: hides soft-deleted rows."""

    # exclude soft-deleted rows
    def get_queryset(self):
        return FinancialRecordQuerySet(self.model, using=self._db).active_only()

    # include soft-deleted rows
    def all_including_deleted(self):
        return FinancialRecordQuerySet(self.model, using=self._db)


class FinancialRecord(models.Model):
    class EntryType(models.TextChoices):
        INCOME = "income", "Income"
        EXPENSE = "expense", "Expense"

    amount = models.DecimalField(max_digits=14, decimal_places=2)
    type = models.CharField(max_length=20, choices=EntryType.choices)
    category = models.CharField(max_length=128)
    occurred_at = models.DateTimeField()
    notes = models.TextField(blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="financial_records",
    )
    deleted_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = FinancialRecordManager()
    all_objects = models.Manager()

    class Meta:
        ordering = ("-occurred_at", "-id")
        indexes = [
            models.Index(fields=["occurred_at"]),
            models.Index(fields=["category"]),
            models.Index(fields=["type"]),
            models.Index(fields=["deleted_at"]),
        ]

    def __str__(self):
        return f"{self.type} {self.amount} @ {self.occurred_at:%Y-%m-%d}"
