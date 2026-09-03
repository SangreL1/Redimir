from django.urls import path
from .views import (
    GeneradorPageView, VerificarCertificadoView,
    descargar_certificado, ListaCertificadosView,
    EcoEquivalenciaGeneradorView, api_datos_empresa_mes,
)

urlpatterns = [
    path('certificados/', ListaCertificadosView.as_view(), name='certificado-lista'),
    path('certificados/crear/', GeneradorPageView.as_view(), name='certificado-crear'),
    path('certificados/descargar/<int:certificado_id>/', descargar_certificado, name='descargar_certificado'),
    path('verificar/<str:codigo>/', VerificarCertificadoView.as_view(), name='certificado-verificar'),
    # Eco-Equivalencia
    path('certificados/eco/', EcoEquivalenciaGeneradorView.as_view(), name='eco-equivalencia'),
    path('certificados/eco/datos/', api_datos_empresa_mes, name='eco-datos-empresa'),
]
