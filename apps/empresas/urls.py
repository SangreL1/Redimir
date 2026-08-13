from django.urls import path
from .views import (
    EmpresaListView, EmpresaDeleteView,
    EmpresaPortalView, EmpresaSolicitudCrearView, EmpresaSolicitudListView, EmpresaGuiaReciclajeView,
    SolicitudListView, SolicitudCrearView,
    SolicitudAceptarView, SolicitudCompletarView, SolicitudCancelarView,
    EstadoDePagoListView, EstadoDePagoCrearView,
    EstadoDePagoDetalleView, EstadoDePagoEditarView, EstadoDePagoAnularView, EstadoDePagoEliminarView,
    TarifaEmpresaGestionView, APITarifasEmpresaView,
)

urlpatterns = [
    # Admin: empresa management
    path('empresas/', EmpresaListView.as_view(), name='empresa-list'),
    path('empresas/<int:pk>/eliminar/', EmpresaDeleteView.as_view(), name='empresa-delete'),

    # Empresa portal (rol='empresa')
    path('empresa/dashboard/', EmpresaPortalView.as_view(), name='empresa-portal'),
    path('empresa/solicitudes/', EmpresaSolicitudListView.as_view(), name='empresa-solicitudes'),
    path('empresa/solicitudes/crear/', EmpresaSolicitudCrearView.as_view(), name='empresa-solicitud-crear'),
    path('empresa/como-reciclar/', EmpresaGuiaReciclajeView.as_view(), name='empresa-guia-reciclaje'),

    # Admin + recolector: solicitudes management
    path('solicitudes/', SolicitudListView.as_view(), name='solicitud-lista'),
    path('solicitudes/crear/', SolicitudCrearView.as_view(), name='solicitud-crear'),
    path('solicitudes/<int:pk>/aceptar/', SolicitudAceptarView.as_view(), name='solicitud-aceptar'),
    path('solicitudes/<int:pk>/completar/', SolicitudCompletarView.as_view(), name='solicitud-completar'),
    path('solicitudes/<int:pk>/cancelar/', SolicitudCancelarView.as_view(), name='solicitud-cancelar'),

    # Estados de Pago Internos & Tarifarios
    path('estados-de-pago/', EstadoDePagoListView.as_view(), name='estados-de-pago-lista'),
    path('estados-de-pago/crear/', EstadoDePagoCrearView.as_view(), name='estados-de-pago-crear'),
    path('estados-de-pago/<int:pk>/', EstadoDePagoDetalleView.as_view(), name='estados-de-pago-detalle'),
    path('estados-de-pago/<int:pk>/editar/', EstadoDePagoEditarView.as_view(), name='estados-de-pago-editar'),
    path('estados-de-pago/<int:pk>/anular/', EstadoDePagoAnularView.as_view(), name='estados-de-pago-anular'),
    path('estados-de-pago/<int:pk>/eliminar/', EstadoDePagoEliminarView.as_view(), name='estados-de-pago-eliminar'),
    path('empresas/tarifas/', TarifaEmpresaGestionView.as_view(), name='tarifas-empresa'),

    # API Tarifario en tiempo real
    path('api/empresas/<int:pk>/tarifas/', APITarifasEmpresaView.as_view(), name='api-empresa-tarifas'),
]


