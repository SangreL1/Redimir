from django.urls import path
from .views import RecoleccionPageView, LoteDetallePageView, LoteListView, LoteProcesarPageView, LoteEditarView

urlpatterns = [
    path('recolecciones/crear/', RecoleccionPageView.as_view(), name='recoleccion-crear'),
    path('recolecciones/', LoteListView.as_view(), name='recoleccion-lista'),
    path('lotes/<str:codigo_lote>/', LoteDetallePageView.as_view(), name='lote-detalle'),
    path('lotes/<str:codigo_lote>/editar/', LoteEditarView.as_view(), name='lote-editar'),
    path('lotes/<str:codigo_lote>/procesar/', LoteProcesarPageView.as_view(), name='lote-procesar'),
]

