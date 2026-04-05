from django.utils import timezone
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.permissions import CanAccessDashboard, IsAdmin, IsAnalystOrAdmin
from finance.filters import FinancialRecordFilter
from finance.models import FinancialRecord
from finance.serializers import FinancialRecordSerializer
from finance.services import build_dashboard_summary, parse_dashboard_query_params


class FinancialRecordViewSet(viewsets.ModelViewSet):
    """
    Records: read for analyst+admin; write for admin only.
    List supports django-filter: date_from, date_to, category, type.

    ``DELETE .../records/{id}/`` — soft delete (sets ``deleted_at``) (admin only).
    ``DELETE .../records/{id}/permanent/`` — hard delete (admin only); works for
    active or already soft-deleted rows.
    """

    serializer_class = FinancialRecordSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend]
    filterset_class = FinancialRecordFilter

    def get_queryset(self):
        if getattr(self, "action", None) == "permanent_delete":
            return FinancialRecord.all_objects.all()
        return FinancialRecord.objects.all()

    def get_permissions(self):
        if self.action in ("list", "retrieve"):
            return [IsAuthenticated(), IsAnalystOrAdmin()]
        return [IsAuthenticated(), IsAdmin()]

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)

    def perform_destroy(self, instance):
        instance.deleted_at = timezone.now()
        instance.save(update_fields=["deleted_at", "updated_at"])

    @action(detail=True, methods=["delete"], url_path="permanent")
    def permanent_delete(self, request, *args, **kwargs):
        instance = self.get_object()
        instance.delete()
        return Response(status=204)


class DashboardSummaryView(APIView):
    """
    Dashboard aggregates — viewer, analyst, admin.

    Query: ``date_from``, ``date_to`` (``YYYY-MM-DD``, UTC calendar-day inclusive),
    ``recent_limit`` (default 10, max 50).
    """

    permission_classes = [IsAuthenticated, CanAccessDashboard]

    def get(self, request):
        date_from, date_to, recent_limit = parse_dashboard_query_params(
            request.query_params
        )
        payload = build_dashboard_summary(
            date_from=date_from,
            date_to=date_to,
            recent_limit=recent_limit,
        )
        return Response(payload)
