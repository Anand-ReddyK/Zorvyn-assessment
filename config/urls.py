"""
URL configuration for config project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""

from django.contrib import admin
from django.urls import include, path
from rest_framework.routers import DefaultRouter

from accounts.jwt_throttled_views import (
    ThrottledTokenObtainPairView,
    ThrottledTokenRefreshView,
)
from accounts.views import UserViewSet
from finance.views import DashboardSummaryView, FinancialRecordViewSet

router = DefaultRouter()
router.register(r"users", UserViewSet, basename="user")
router.register(r"records", FinancialRecordViewSet, basename="financialrecord")

urlpatterns = [
    path("admin/", admin.site.urls),
    path(
        "api/auth/token/",
        ThrottledTokenObtainPairView.as_view(),
        name="token_obtain_pair",
    ),
    path(
        "api/auth/token/refresh/",
        ThrottledTokenRefreshView.as_view(),
        name="token_refresh",
    ),
    path(
        "api/dashboard/summary/",
        DashboardSummaryView.as_view(),
        name="dashboard-summary",
    ),
    path("api/", include(router.urls)),
]
