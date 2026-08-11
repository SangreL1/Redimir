from django.urls import path
from .views import GeneradorPageView, VerificarCertificadoView

urlpatterns = [
    path('certificados/crear/', GeneradorPageView.as_view(), name='certificado-crear'),
    path('verificar/<str:codigo>/', VerificarCertificadoView.as_view(), name='certificado-verificar'),
]

