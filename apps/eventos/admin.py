from django.contrib import admin
from .models import Evento

@admin.register(Evento)
class EventoAdmin(admin.ModelAdmin):
    list_display = ('lote', 'tipo_evento', 'usuario', 'timestamp')
    list_filter = ('tipo_evento', 'timestamp')
    search_fields = ('lote__codigo_lote',)
