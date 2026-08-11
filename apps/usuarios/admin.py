from django.contrib import admin
from .models import Usuario, AuditLog

@admin.register(Usuario)
class UsuarioAdmin(admin.ModelAdmin):
    list_display = ('email', 'nombre', 'apellido', 'rol', 'empresa', 'is_active')
    list_filter = ('rol', 'is_active', 'empresa')
    search_fields = ('email', 'nombre', 'apellido')

@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ('fecha_registro', 'usuario', 'accion', 'modelo', 'registro_id', 'campo_modificado', 'ip_origen')
    list_filter = ('accion', 'modelo', 'fecha_registro')
    search_fields = ('modelo', 'registro_id', 'detalles', 'usuario__email', 'usuario__rut')
    readonly_fields = ('usuario', 'accion', 'modelo', 'registro_id', 'campo_modificado', 'valor_anterior', 'valor_nuevo', 'detalles', 'ip_origen', 'fecha_registro')

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

