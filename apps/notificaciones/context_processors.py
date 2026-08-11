def notificaciones_no_leidas(request):
    """Injects unread notification count & active solicitudes count into every template context."""
    if request.user.is_authenticated:
        try:
            count = request.user.notificaciones.filter(leida=False).count()
        except Exception:
            count = 0
            
        sols_activas = 0
        if request.user.rol == 'recolector':
            from apps.empresas.models import SolicitudRecoleccion
            sols_activas = SolicitudRecoleccion.objects.filter(
                operador_asignado=request.user, estado='asignada'
            ).count()
            
        return {
            'notif_sin_leer': count,
            'solicitudes_activas_count': sols_activas
        }
    return {'notif_sin_leer': 0, 'solicitudes_activas_count': 0}
