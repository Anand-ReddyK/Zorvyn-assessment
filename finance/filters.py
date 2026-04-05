"""Query filters for financial record list API."""

import django_filters

from finance.models import FinancialRecord


class FinancialRecordFilter(django_filters.FilterSet):
    """
    Query params: `date_from`, `date_to` (calendar dates, UTC `occurred_at` date,
    inclusive), `category`, `type`.
    """

    date_from = django_filters.DateFilter(
        field_name="occurred_at",
        lookup_expr="date__gte",
    )
    date_to = django_filters.DateFilter(
        field_name="occurred_at",
        lookup_expr="date__lte",
    )
    category = django_filters.CharFilter(field_name="category", lookup_expr="exact")
    type = django_filters.ChoiceFilter(
        field_name="type",
        choices=FinancialRecord.EntryType.choices,
    )

    class Meta:
        model = FinancialRecord
        fields = ()
