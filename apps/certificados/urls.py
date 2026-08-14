from django.urls import path
from .views import GeneradorPageView, VerificarCertificadoView, descargar_certificado, ListaCertificadosView

urlpatterns = [
    path('certificados/', ListaCertificadosView.as_view(), name='certificado-lista'),
    path('certificados/crear/', GeneradorPageView.as_view(), name='certificado-crear'),
    path('certificados/descargar/<int:certificado_id>/', descargar_certificado, name='descargar_certificado'),
    path('verificar/<str:codigo>/', VerificarCertificadoView.as_view(), name='certificado-verificar'),
]
