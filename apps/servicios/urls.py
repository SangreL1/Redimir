from django.urls import path
from .views import (
    CrearServicioView, ListaServiciosView, DetalleServicioView,
    RegistrarRetiroView, RegistroExitosoView, ValidacionesPendientesView,
    EditarServicioRegistroView, ServicioEnviarEmailView,
)
from .views_retiros import (
    retiros_lista, retiro_crear, retiro_detalle,
    retiro_editar, retiro_eliminar,
    retiros_informe, exportar_retiros_excel,
    api_materiales_retiro, galeria_fotos,
    migrar_lotes_a_tickets_view
)

urlpatterns = [
    # Servicios CRUD
    path('servicios/crear/',              CrearServicioView.as_view(),       name='servicio-crear'),
    path('servicios/',                    ListaServiciosView.as_view(),       name='servicios-lista'),
    path('servicios/<int:pk>/',           DetalleServicioView.as_view(),      name='servicio-detalle'),
    path('servicios/<int:pk>/editar/',    EditarServicioRegistroView.as_view(), name='servicio-editar'),
    path('servicios/<int:pk>/enviar-email/', ServicioEnviarEmailView.as_view(), name='servicio-enviar-email'),

    # Flujo operador
    path('servicios/<int:pk>/registrar/', RegistrarRetiroView.as_view(),      name='registrar-retiro'),
    path('servicios/<int:pk>/exito/',     RegistroExitosoView.as_view(),      name='registro-exitoso'),

    # Validaciones admin
    path('validaciones/',                 ValidacionesPendientesView.as_view(), name='validaciones'),

    # NUEVO MÓDULO REDIMIR: Gestión relacional de Retiros y Tickets
    path('retiros/',                      retiros_lista,          name='retiros-lista'),
    path('retiros/nuevo/',                retiro_crear,           name='retiro-crear'),
    path('retiros/<int:pk>/',             retiro_detalle,         name='retiro-detalle'),
    path('retiros/<int:pk>/editar/',      retiro_editar,          name='retiro-editar'),
    path('retiros/<int:pk>/eliminar/',    retiro_eliminar,        name='retiro-eliminar'),
    path('retiros/informe/',              retiros_informe,        name='retiros-informe'),
    path('retiros/informe/excel/',        exportar_retiros_excel, name='retiros-informe-excel'),
    path('retiros/galeria/',              galeria_fotos,          name='retiros-galeria'),
    path('galeria/',                      galeria_fotos,          name='galeria-fotos'),
    path('retiros/sincronizar-lotes/',    migrar_lotes_a_tickets_view, name='retiros-sincronizar-lotes'),
    path('api/retiros/materiales/',       api_materiales_retiro,  name='retiros-api-materiales'),
]
