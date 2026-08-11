from django.contrib import admin
from .models import Empresa

@admin.register(Empresa)
class EmpresaAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'rut', 'email_contacto', 'rubro', 'estado', 'activa')
    list_filter = ('activa', 'estado', 'rubro')
    search_fields = ('nombre', 'rut', 'email_contacto')
