from decimal import Decimal

from django.utils import timezone
from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.permissions import CanAccessDashboard, IsAdmin, IsAnalystOrAdmin
from finance.models import FinancialRecord
from finance.serializers import FinancialRecordSerializer


class FinancialRecordViewSet(viewsets.ModelViewSet):
    """
    Records: read for analyst+admin; write for admin only.
    """

    serializer_class = FinancialRecordSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
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


class DashboardSummaryView(APIView):
    """
    Dashboard aggregates — all roles with CanAccessDashboard.
    Placeholder body until full analytics are implemented.
    """

    permission_classes = [IsAuthenticated, CanAccessDashboard]

    def get(self, request):
        empty = Decimal("0.00")
        return Response(
            {
                "totals": {
                    "income": f"{empty:.2f}",
                    "expense": f"{empty:.2f}",
                    "net": f"{empty:.2f}",
                },
                "by_category": [],
                "recent_activity": [],
                "monthly_trend": [],
            }
        )
