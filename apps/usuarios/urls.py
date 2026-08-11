from django.urls import path
from .views import (
    LoginPageView, LogoutView,
    RegistroEmpresaView, RegistroTrabajadorView,
    GestionAccesosView,
    BuscarTrabajadorView, FichaTrabajadorView,
    AuditLogsView,
)

urlpatterns = [
    path('login/',                      LoginPageView.as_view(),        name='login-page'),
    path('logout/',                     LogoutView.as_view(),            name='logout'),
    path('registro/empresa/',           RegistroEmpresaView.as_view(),   name='registro-empresa'),
    path('registro/trabajador/',        RegistroTrabajadorView.as_view(),name='registro-trabajador'),
    # Renamed from 'admin/accesos/' to 'gestion/accesos/' to avoid Django admin URL conflict
    path('gestion/accesos/',            GestionAccesosView.as_view(),    name='gestion-accesos'),
    path('gestion/trabajadores/',       BuscarTrabajadorView.as_view(),  name='buscar-trabajador'),
    path('gestion/trabajadores/<int:pk>/', FichaTrabajadorView.as_view(), name='ficha-trabajador'),
    path('gestion/auditoria/',          AuditLogsView.as_view(),         name='audit-logs'),
]

