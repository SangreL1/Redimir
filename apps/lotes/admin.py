from django.contrib import admin
from .models import Lote

@admin.register(Lote)
class LoteAdmin(admin.ModelAdmin):
    list_display = ('codigo_lote', 'empresa_origen', 'tipo_residuo', 'cantidad_kg', 'estado', 'fecha_creacion')
    list_filter = ('estado', 'tipo_residuo', 'empresa_origen')
    search_fields = ('codigo_lote', 'qr_code')
