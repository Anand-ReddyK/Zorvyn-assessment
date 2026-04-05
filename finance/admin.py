from django.contrib import admin

from finance.models import FinancialRecord


@admin.register(FinancialRecord)
class FinancialRecordAdmin(admin.ModelAdmin):
    readonly_fields = ("created_by", "created_at", "updated_at")

    def save_model(self, request, obj, form, change):
        if not change:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)

    list_display = (
        "id",
        "amount",
        "type",
        "category",
        "occurred_at",
        "created_by",
        "deleted_at",
        "created_at",
    )
    list_filter = ("type", "category")
    search_fields = ("category", "notes")
    date_hierarchy = "occurred_at"
