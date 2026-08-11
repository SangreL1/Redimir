from django.urls import path
from .views import (
    DashboardPageView, DashboardAdminView, DashboardOperadorView,
    DetalleOperadorView, ExportarExcelAPIView, CierreMensualView, ExportarZipAPIView
)

urlpatterns = [
    path('dashboard/', DashboardPageView.as_view(), name='dashboard'),
    path('dashboard/admin/', DashboardAdminView.as_view(), name='dashboard-admin'),
    path('dashboard/recolector/', DashboardOperadorView.as_view(), name='dashboard-recolector'),
    path('dashboard/operador/', DashboardOperadorView.as_view(), name='dashboard-operador'),
    path('dashboard/operadores/<int:pk>/', DetalleOperadorView.as_view(), name='detalle-operador'),
    path('api/reportes/exportar-excel/', ExportarExcelAPIView.as_view(), name='api-exportar'),
    path('api/reportes/exportar-zip/', ExportarZipAPIView.as_view(), name='api-exportar-zip'),
    path('cierre-mensual/', CierreMensualView.as_view(), name='cierre-mensual'),
]

