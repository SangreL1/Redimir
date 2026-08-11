from django.contrib import admin
from .models import Certificado

@admin.register(Certificado)
class CertificadoAdmin(admin.ModelAdmin):
    list_display = ('codigo_certificado', 'empresa', 'total_rsd_kg', 'numero_servicios', 'fecha_generacion')
    list_filter = ('empresa', 'fecha_generacion')
    search_fields = ('codigo_certificado',)
