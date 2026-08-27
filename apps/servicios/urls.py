from django.urls import path
from .views import (
    CrearServicioView, ListaServiciosView, DetalleServicioView,
    RegistrarRetiroView, RegistroExitosoView, ValidacionesPendientesView,
    EditarServicioRegistroView,
)

urlpatterns = [
    # Servicios CRUD
    path('servicios/crear/',              CrearServicioView.as_view(),       name='servicio-crear'),
    path('servicios/',                    ListaServiciosView.as_view(),       name='servicios-lista'),
    path('servicios/<int:pk>/',           DetalleServicioView.as_view(),      name='servicio-detalle'),
    path('servicios/<int:pk>/editar/',    EditarServicioRegistroView.as_view(), name='servicio-editar'),

    # Flujo operador
    path('servicios/<int:pk>/registrar/', RegistrarRetiroView.as_view(),      name='registrar-retiro'),
    path('servicios/<int:pk>/exito/',     RegistroExitosoView.as_view(),      name='registro-exitoso'),

    # Validaciones admin
    path('validaciones/',                 ValidacionesPendientesView.as_view(), name='validaciones'),
]

